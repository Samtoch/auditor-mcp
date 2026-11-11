"""Command line for the gateway: ``uv run auditor-gateway <command>``.

Commands:
    serve                    run the gateway over stdio (default; used by Claude Desktop)
    refresh                  connect to the servers and record their current tools
    pins                     list every tool and its status
    show SERVER TOOL         show a tool's definition, and what changed since approval
    approve SERVER [TOOL]    approve the tool's current definition (or --all for the server)
    revoke SERVER TOOL       withdraw approval
"""

from __future__ import annotations

import argparse
import difflib
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

import anyio
from mcp.server.stdio import stdio_server

from auditor_mcp import __version__
from auditor_mcp.config import DEFAULT_LOG_LEVEL
from auditor_mcp.gateway.config import GatewayConfig
from auditor_mcp.gateway.proxy import Gateway
from auditor_mcp.logging_setup import configure_logging
from auditor_mcp.security import PinRecord, PinStatus, PinStore
from auditor_mcp.storage.events import JsonlEventLog

logger = logging.getLogger(__name__)


def build_gateway(config: GatewayConfig) -> Gateway:
    return Gateway(config, PinStore(config.pins_file), JsonlEventLog(config.events_file))


# --- commands ---------------------------------------------------------------


async def _serve(config: GatewayConfig) -> None:
    gateway = build_gateway(config)
    logger.info("auditor-gateway %s starting; pins: %s", __version__, config.pins_file)
    async with stdio_server() as (read_stream, write_stream):
        await gateway.server.run(
            read_stream, write_stream, gateway.server.create_initialization_options()
        )


async def _refresh(config: GatewayConfig) -> int:
    gateway = build_gateway(config)
    async with gateway.server.lifespan(gateway.server):
        for name, error in gateway.pool.failures.items():
            print(f"{name}: could not start ({error})")
        for name in gateway.pool.connected:
            await gateway.sync_server(name)
    return _pins(config)


def _pins(config: GatewayConfig) -> int:
    records = PinStore(config.pins_file).all()
    if not records:
        print("No tools recorded yet. Run 'auditor-gateway refresh'.")
        return 0
    width = max(len(r.key) for r in records)
    print(f"{'TOOL':<{width}}  {'STATUS':<9}  FINGERPRINT")
    for r in records:
        print(f"{r.key:<{width}}  {r.status.value:<9}  {r.observed_fingerprint[:12]}")
    pending = [r for r in records if not r.is_trusted]
    if pending:
        print(f"\n{len(pending)} tool(s) quarantined. Review with 'show', then 'approve'.")
    return 0


def _show(config: GatewayConfig, server: str, tool: str) -> int:
    record = PinStore(config.pins_file).get(server, tool)
    if record is None:
        print(f"No record for {server}/{tool}.")
        return 1
    print(f"{record.key}  status={record.status.value}")
    print(f"observed fingerprint: {record.observed_fingerprint}")
    print(f"approved fingerprint: {record.approved_fingerprint or '(never approved)'}\n")
    if record.status is PinStatus.CHANGED and record.approved_definition:
        print("Changes since approval:")
        print(_diff(record))
    else:
        print(json.dumps(record.observed_definition, indent=2, ensure_ascii=False))
    print(
        "\nRead the description and every parameter description carefully: look for "
        "instructions to the model, references to files, secrets or other tools, and "
        "hidden or encoded text."
    )
    return 0


def _approve(
    config: GatewayConfig, server: str, tool: str | None, approve_all: bool, fingerprint: str | None
) -> int:
    store = PinStore(config.pins_file)
    if approve_all:
        targets = [r for r in store.all() if r.server == server and not r.is_trusted]
        if not targets:
            print(f"Nothing to approve for {server}.")
            return 0
    elif tool:
        record = store.get(server, tool)
        if record is None:
            print(f"No record for {server}/{tool}. Run 'auditor-gateway refresh' first.")
            return 1
        targets = [record]
    else:
        print("Give a TOOL name, or --all to approve every quarantined tool of the server.")
        return 2

    for record in targets:
        try:
            store.approve(record.server, record.tool, expected_fingerprint=fingerprint)
        except ValueError as exc:
            print(exc)
            return 1
        print(f"Approved {record.key} ({record.observed_fingerprint[:12]})")
    print("Restart Claude Desktop (or start a new chat) so it re-lists the tools.")
    return 0


def _revoke(config: GatewayConfig, server: str, tool: str) -> int:
    try:
        PinStore(config.pins_file).revoke(server, tool)
    except KeyError as exc:
        print(exc.args[0])
        return 1
    print(f"Revoked {server}/{tool}.")
    return 0


def _diff(record: PinRecord) -> str:
    def lines(definition: dict) -> list[str]:
        return json.dumps(definition, indent=2, ensure_ascii=False, sort_keys=True).splitlines()

    return "\n".join(
        difflib.unified_diff(
            lines(record.approved_definition or {}),
            lines(record.observed_definition),
            fromfile="approved",
            tofile="observed",
            lineterm="",
        )
    )


# --- entry point ------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auditor-gateway", description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, help="path to gateway.toml")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="run the gateway over stdio (default)")
    sub.add_parser("refresh", help="record the servers' current tools")
    sub.add_parser("pins", help="list tools and their status")
    show = sub.add_parser("show", help="show a tool's definition and changes")
    show.add_argument("server")
    show.add_argument("tool")
    approve = sub.add_parser("approve", help="approve a tool's current definition")
    approve.add_argument("server")
    approve.add_argument("tool", nargs="?")
    approve.add_argument("--all", action="store_true", help="approve every quarantined tool")
    approve.add_argument("--fingerprint", help="only approve if the fingerprint starts with this")
    revoke = sub.add_parser("revoke", help="withdraw approval")
    revoke.add_argument("server")
    revoke.add_argument("tool")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    configure_logging(DEFAULT_LOG_LEVEL)  # stderr only; stdout belongs to MCP in serve mode
    config = GatewayConfig.load(args.config)

    match args.command:
        case None | "serve":
            anyio.run(_serve, config)
            return 0
        case "refresh":
            return anyio.run(_refresh, config)
        case "pins":
            return _pins(config)
        case "show":
            return _show(config, args.server, args.tool)
        case "approve":
            return _approve(config, args.server, args.tool, args.all, args.fingerprint)
        case "revoke":
            return _revoke(config, args.server, args.tool)
    return 2


if __name__ == "__main__":
    sys.exit(main())
