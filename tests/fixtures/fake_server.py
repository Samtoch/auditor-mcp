"""A downstream MCP server for tests, run as a real subprocess over stdio.

It re-reads its tool definitions from the JSON file named by FAKE_TOOLS_FILE
on every tools/list call, so a test can change a definition mid-session to
simulate a rug pull. Every tool echoes its arguments back.
"""

import json
import os
from pathlib import Path
from typing import Any

import anyio
from mcp.server import Server, ServerRequestContext
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
)

TOOLS_FILE = Path(os.environ["FAKE_TOOLS_FILE"])


async def list_tools(
    ctx: ServerRequestContext[Any], params: PaginatedRequestParams | None
) -> ListToolsResult:
    definitions = json.loads(TOOLS_FILE.read_text(encoding="utf-8"))
    return ListToolsResult(tools=[Tool.model_validate(d) for d in definitions])


async def call_tool(
    ctx: ServerRequestContext[Any], params: CallToolRequestParams
) -> CallToolResult:
    text = f"{params.name} received {json.dumps(params.arguments or {}, sort_keys=True)}"
    return CallToolResult(content=[TextContent(type="text", text=text)])


server = Server("fake", on_list_tools=list_tools, on_call_tool=call_tool)


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
