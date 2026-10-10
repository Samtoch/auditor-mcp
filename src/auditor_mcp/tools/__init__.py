"""MCP tool definitions. Each module exposes a ``register_*`` function."""

from auditor_mcp.tools.audit_tools import register_audit_tools

__all__ = ["register_audit_tools"]
