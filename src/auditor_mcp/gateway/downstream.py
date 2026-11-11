"""Connections from the gateway to the real (downstream) MCP servers."""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from types import TracebackType
from typing import Any

from mcp import Client, StdioServerParameters
from mcp.types import CallToolResult, Tool

from auditor_mcp.gateway.config import DownstreamServer

logger = logging.getLogger(__name__)


class DownstreamUnavailableError(RuntimeError):
    pass


class DownstreamPool:
    """Opens one MCP client per configured server and keeps them for the session.

    A server that fails to start is recorded in ``failures`` and skipped, so
    one broken server doesn't take the whole gateway down.
    """

    def __init__(self, servers: list[DownstreamServer], call_timeout_seconds: float = 60.0) -> None:
        self._servers = {s.name: s for s in servers}
        self._timeout = call_timeout_seconds
        self._clients: dict[str, Client] = {}
        self.failures: dict[str, str] = {}
        self._stack = AsyncExitStack()

    @property
    def connected(self) -> list[str]:
        return list(self._clients)

    async def __aenter__(self) -> DownstreamPool:
        await self._stack.__aenter__()
        for server in self._servers.values():
            try:
                client = Client(
                    StdioServerParameters(
                        command=server.command,
                        args=server.args,
                        cwd=server.cwd,
                        env=server.env,
                    ),
                    read_timeout_seconds=self._timeout,
                )
                self._clients[server.name] = await self._stack.enter_async_context(client)
                logger.info("Connected to downstream server %r", server.name)
            except Exception as exc:  # any startup failure: bad path, crash, handshake error
                cause = _root_cause(exc)
                self.failures[server.name] = f"{type(cause).__name__}: {cause}"
                logger.error("Could not start downstream server %r: %s", server.name, cause)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._stack.__aexit__(exc_type, exc, tb)
        self._clients.clear()

    async def list_tools(self, server: str) -> list[Tool]:
        client = self._client(server)
        tools: list[Tool] = []
        cursor: str | None = None
        while True:
            # cache_mode="refresh": always ask the server, never a cached list,
            # otherwise a changed definition could go unnoticed.
            page = await client.list_tools(cursor=cursor, cache_mode="refresh")
            tools.extend(page.tools)
            cursor = page.next_cursor
            if not cursor:
                return tools

    async def call_tool(self, server: str, tool: str, arguments: dict[str, Any]) -> CallToolResult:
        return await self._client(server).call_tool(tool, arguments)

    def _client(self, server: str) -> Client:
        try:
            return self._clients[server]
        except KeyError:
            raise DownstreamUnavailableError(f"Server {server!r} is not connected.") from None


def _root_cause(exc: BaseException) -> BaseException:
    """Unwrap task-group exception groups to the first real error."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return exc
