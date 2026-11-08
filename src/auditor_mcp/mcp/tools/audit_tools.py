"""Audit tools: log_query, log_response, get_recent_turns.

This module is the MCP-facing layer only. It describes the tools to the
model and formats results; the rules live in AuditService.
"""

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from auditor_mcp.models.audit import AuditEntry, Turn
from auditor_mcp.services import AuditService


def register_audit_tools(mcp: MCPServer, service: AuditService) -> None:
    """Register the audit tools on ``mcp``, backed by ``service``."""
    limit = service.word_limit

    text_rule = (
        f"Verbatim if it is {limit} words or fewer; "
        f"otherwise a faithful summary of at most {limit} words."
    )
    summary_flag = "True if text is a summary rather than the original wording."
    count_hint = "Approximate word count of the original text. Required when is_summary is true."

    @mcp.tool(
        description=(
            "Record the user's latest message in the audit log. Call this first, "
            "every turn, before any other tool. Returns a turn_id to pass to log_response."
        ),
        annotations=ToolAnnotations(title="Log query", read_only_hint=False),
    )
    def log_query(
        text: Annotated[str, Field(description=f"The user's message. {text_rule}")],
        is_summary: Annotated[bool, Field(description=summary_flag)] = False,
        original_word_count: Annotated[int | None, Field(description=count_hint, ge=0)] = None,
    ) -> str:
        entry = service.record_query(text, is_summary, original_word_count)
        return f"Logged. turn_id: {entry.turn_id}"

    @mcp.tool(
        description=(
            "Record your answer for the current turn. Call this last, after you have "
            "written your answer."
        ),
        annotations=ToolAnnotations(title="Log response", read_only_hint=False),
    )
    def log_response(
        turn_id: Annotated[str, Field(description="The turn_id returned by log_query.")],
        text: Annotated[str, Field(description=f"Your answer. {text_rule}")],
        is_summary: Annotated[bool, Field(description=summary_flag)] = False,
        original_word_count: Annotated[int | None, Field(description=count_hint, ge=0)] = None,
    ) -> str:
        service.record_response(turn_id, text, is_summary, original_word_count)
        return "Logged."

    @mcp.tool(
        description="Show the most recent logged turns, each query paired with its response.",
        annotations=ToolAnnotations(title="Recent turns", read_only_hint=True),
    )
    def get_recent_turns(
        limit: Annotated[int, Field(description="How many turns to return.", ge=1, le=100)] = 10,
    ) -> str:
        turns = service.recent_turns(limit)
        return format_turns(turns) if turns else "The audit log is empty."


def format_turns(turns: list[Turn]) -> str:
    lines: list[str] = []
    for turn in turns:
        lines.append(f"[{turn.query.timestamp}] Q: {_display(turn.query)}")
        if turn.response:
            lines.append(f"    A: {_display(turn.response)}")
        else:
            lines.append("    A: (no response logged)")
    return "\n".join(lines)


def _display(entry: AuditEntry) -> str:
    return f"(summary) {entry.text}" if entry.is_summary else entry.text
