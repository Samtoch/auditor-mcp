"""Entry file for the MCP Inspector: ``uv run mcp dev dev.py``.

``mcp dev`` looks for a module-level variable called ``mcp``. The real
entry point for Claude Desktop is the ``auditor-mcp`` script.
"""

from app.logging_setup import configure_logging
from app.mcp.server import create_server

configure_logging()
mcp = create_server()
