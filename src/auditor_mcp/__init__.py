"""auditor-mcp: an MCP server that keeps an audit log of conversation turns."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("auditor-mcp")
except PackageNotFoundError:  # running from a source tree that isn't installed
    __version__ = "0.0.0"

__all__ = ["__version__"]
