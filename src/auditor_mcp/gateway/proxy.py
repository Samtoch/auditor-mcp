"""The gateway: one MCP server that fronts the downstream servers.

Claude Desktop connects only to the gateway. The gateway

1. lists each downstream server's tools and checks them against the pin store,
2. exposes only tools whose live definition matches the approved one,
3. re-checks the definition immediately before forwarding every call, and
4. writes every decision to the security event log from code, not from the model.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from mcp.server import Server, ServerRequestContext
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
)

from auditor_mcp import __version__
from auditor_mcp.gateway.config import NAMESPACE_SEPARATOR, GatewayConfig
from auditor_mcp.gateway.downstream import DownstreamPool
from auditor_mcp.security import PinRecord, PinStatus, PinStore, to_definition
from auditor_mcp.security.pins import Observation
from auditor_mcp.storage.events import EventType, GatewayEvent, JsonlEventLog

logger = logging.getLogger(__name__)

MAX_LOGGED_STRING = 500

INSTRUCTIONS = (
    "Tools from other servers are provided through the auditor gateway and are named "
    f"<server>{NAMESPACE_SEPARATOR}<tool>. If a call is blocked because a tool is quarantined, "
    "tell the user which tool and why. Do not try to work around the block."
)

_STATUS_EVENTS = {
    PinStatus.NEW: EventType.TOOL_NEW,
    PinStatus.CHANGED: EventType.TOOL_CHANGED,
    PinStatus.APPROVED: EventType.TOOL_RESTORED,
}


def namespaced(server: str, tool: str) -> str:
    return f"{server}{NAMESPACE_SEPARATOR}{tool}"


def split_name(name: str) -> tuple[str, str] | None:
    server, sep, tool = name.partition(NAMESPACE_SEPARATOR)
    return (server, tool) if sep and server and tool else None


class Gateway:
    def __init__(
        self,
        config: GatewayConfig,
        pins: PinStore,
        events: JsonlEventLog,
        *,
        pool_factory: Callable[[GatewayConfig], DownstreamPool] | None = None,
    ) -> None:
        self._config = config
        self._pins = pins
        self._events = events
        self._pool_factory = pool_factory or (
            lambda c: DownstreamPool(c.servers, c.call_timeout_seconds)
        )
        self._pool: DownstreamPool | None = None
        self.server: Server[Any] = Server(
            "auditor-gateway",
            version=__version__,
            instructions=INSTRUCTIONS,
            lifespan=self._lifespan,
            on_list_tools=self._on_list_tools,
            on_call_tool=self._on_call_tool,
        )

    # --- lifecycle ---------------------------------------------------------

    @asynccontextmanager
    async def _lifespan(self, _: Server[Any]) -> AsyncIterator[dict[str, Any]]:
        self._events.write(
            GatewayEvent(EventType.GATEWAY_STARTED, details={"version": __version__})
        )
        async with self._pool_factory(self._config) as pool:
            self._pool = pool
            for name, error in pool.failures.items():
                self._events.write(
                    GatewayEvent(
                        EventType.SERVER_UNAVAILABLE, server=name, details={"error": error}
                    )
                )
            for name in pool.connected:
                self._events.write(GatewayEvent(EventType.SERVER_CONNECTED, server=name))
            try:
                yield {}
            finally:
                self._pool = None

    @property
    def pool(self) -> DownstreamPool:
        if self._pool is None:
            raise RuntimeError("Gateway is not running.")
        return self._pool

    # --- tool listing ------------------------------------------------------

    async def sync_server(self, server: str) -> dict[str, Tool]:
        """Fetch a server's live tools, update the pin store, return the trusted ones."""
        trusted: dict[str, Tool] = {}
        for tool in await self.pool.list_tools(server):
            observation = self._pins.observe(server, tool.name, to_definition(tool))
            self._report(observation)
            if observation.record.is_trusted:
                trusted[tool.name] = tool
        return trusted

    async def _on_list_tools(
        self, ctx: ServerRequestContext[Any], params: PaginatedRequestParams | None
    ) -> ListToolsResult:
        exposed: list[Tool] = []
        for server in self.pool.connected:
            try:
                trusted = await self.sync_server(server)
            except Exception as exc:
                logger.error("Listing tools from %r failed: %s", server, exc)
                self._events.write(
                    GatewayEvent(
                        EventType.SERVER_UNAVAILABLE, server=server, details={"error": str(exc)}
                    )
                )
                continue
            for name, tool in trusted.items():
                exposed.append(tool.model_copy(update={"name": namespaced(server, name)}))
        return ListToolsResult(tools=exposed)

    # --- tool calls --------------------------------------------------------

    async def _on_call_tool(
        self, ctx: ServerRequestContext[Any], params: CallToolRequestParams
    ) -> CallToolResult:
        call_id = uuid.uuid4().hex[:12]
        arguments = params.arguments or {}
        parts = split_name(params.name)
        if parts is None or parts[0] not in self.pool.connected:
            return self._block(call_id, None, params.name, "unknown tool", arguments)
        server, tool = parts

        # Re-check the live definition right before forwarding, so a definition
        # changed after the last listing is caught before it can be used.
        try:
            await self.sync_server(server)
        except Exception as exc:
            return self._block(call_id, server, tool, f"could not verify tool: {exc}", arguments)

        record = self._pins.get(server, tool)
        if record is None:
            return self._block(call_id, server, tool, "tool not offered by server", arguments)
        if not record.is_trusted:
            return self._block(
                call_id, server, tool, _quarantine_reason(record), arguments, status=record.status
            )

        self._events.write(
            GatewayEvent(
                EventType.TOOL_CALL_ALLOWED,
                server,
                tool,
                call_id=call_id,
                details={
                    "fingerprint": record.approved_fingerprint,
                    "arguments": _summarise(arguments),
                },
            )
        )
        try:
            result = await self.pool.call_tool(server, tool, arguments)
        except Exception as exc:
            self._events.write(
                GatewayEvent(
                    EventType.TOOL_CALL_FAILED,
                    server,
                    tool,
                    call_id=call_id,
                    details={"error": str(exc)},
                )
            )
            return _error_result(f"Call to {params.name} failed: {exc}")

        self._events.write(
            GatewayEvent(
                EventType.TOOL_RESULT,
                server,
                tool,
                call_id=call_id,
                details=_describe_result(result),
            )
        )
        return result

    # --- helpers -----------------------------------------------------------

    def _report(self, observation: Observation) -> None:
        if not observation.status_changed:
            return
        record = observation.record
        event = _STATUS_EVENTS.get(record.status)
        if event is None:
            return
        self._events.write(
            GatewayEvent(
                event,
                record.server,
                record.tool,
                details={
                    "observed_fingerprint": record.observed_fingerprint,
                    "approved_fingerprint": record.approved_fingerprint,
                },
            )
        )
        if record.status is not PinStatus.APPROVED:
            logger.warning("Quarantined %s (%s)", record.key, record.status.value)

    def _block(
        self,
        call_id: str,
        server: str | None,
        tool: str,
        reason: str,
        arguments: dict[str, Any],
        status: PinStatus | None = None,
    ) -> CallToolResult:
        self._events.write(
            GatewayEvent(
                EventType.TOOL_CALL_BLOCKED,
                server,
                tool,
                call_id=call_id,
                details={"reason": reason, "status": status, "arguments": _summarise(arguments)},
            )
        )
        label = namespaced(server, tool) if server else tool
        return _error_result(f"Blocked by auditor gateway: {label}: {reason}.")


def _quarantine_reason(record: PinRecord) -> str:
    match record.status:
        case PinStatus.NEW:
            return "new tool awaiting human approval"
        case PinStatus.CHANGED:
            return "tool definition changed since it was approved (possible rug pull)"
        case PinStatus.REVOKED:
            return "approval was revoked"
        case _:
            return f"tool is not trusted ({record.status.value})"


def _error_result(text: str) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=text)], is_error=True)


def _summarise(value: Any) -> Any:
    """Arguments as logged: long strings are cut, so the log stays readable."""
    if isinstance(value, str) and len(value) > MAX_LOGGED_STRING:
        return f"{value[:MAX_LOGGED_STRING]}... [{len(value)} chars]"
    if isinstance(value, dict):
        return {k: _summarise(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_summarise(v) for v in value]
    return value


def _describe_result(result: CallToolResult) -> dict[str, Any]:
    text = "".join(c.text for c in result.content if isinstance(c, TextContent))
    return {
        "is_error": bool(result.is_error),
        "content_types": sorted({c.type for c in result.content}),
        "text_chars": len(text),
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
