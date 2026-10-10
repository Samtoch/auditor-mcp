"""End-to-end tests through a real MCP client, connected in-process."""

import pytest
from mcp import Client

from auditor_mcp.config import Settings
from auditor_mcp.server import create_server

pytestmark = pytest.mark.anyio


def _text(result) -> str:
    return result.content[0].text


async def test_lists_the_audit_tools(settings: Settings) -> None:
    async with Client(create_server(settings)) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}

    assert set(tools) == {"log_query", "log_response", "get_recent_turns"}
    assert tools["get_recent_turns"].annotations.read_only_hint is True
    assert "turn_id" in tools["log_response"].input_schema["properties"]


async def test_query_and_response_round_trip(settings: Settings) -> None:
    async with Client(create_server(settings)) as client:
        logged = await client.call_tool("log_query", {"text": "What is MCP?"})
        turn_id = _text(logged).removeprefix("Logged. turn_id: ")

        await client.call_tool(
            "log_response",
            {"turn_id": turn_id, "text": "A tool protocol."},
        )
        recent = await client.call_tool("get_recent_turns", {"limit": 5})

    output = _text(recent)
    assert "Q: What is MCP?" in output
    assert "A: A tool protocol." in output
    assert settings.log_file.exists()


async def test_invalid_input_is_reported_as_tool_error(settings: Settings) -> None:
    async with Client(create_server(settings)) as client:
        result = await client.call_tool("log_query", {"text": "   "})

    assert result.is_error
