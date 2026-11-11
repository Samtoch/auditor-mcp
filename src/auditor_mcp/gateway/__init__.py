"""The auditor gateway: a security proxy in front of other MCP servers."""

from auditor_mcp.gateway.config import DownstreamServer, GatewayConfig
from auditor_mcp.gateway.proxy import Gateway

__all__ = ["DownstreamServer", "Gateway", "GatewayConfig"]
