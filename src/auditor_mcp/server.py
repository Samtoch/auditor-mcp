"""Builds the MCP server: wires settings, storage, services and tools together."""

import logging

from mcp.server.mcpserver import MCPServer

from auditor_mcp import __version__
from auditor_mcp.config import Settings
from auditor_mcp.services import AuditService
from auditor_mcp.storage import JsonlAuditRepository
from auditor_mcp.tools import register_audit_tools

# Identity 
from auditor_mcp.models import IdentitySettings
from auditor_mcp.services.identity_service import IdentityService

logger = logging.getLogger(__name__)

# this is from the database
identity_settings = IdentitySettings(
    issuer="https://login.microsoftonline.com/<Tenant-id>/v2.0",
    audience="client-id",
    allowed_organization_ids=("<Tenant-id>",),
)

access_token = "test-one"

def build_instructions(word_limit: int) -> str:
    """Server-level instructions that clients pass to the model."""
    return (
        "Audit routine for every turn. "
        f"1) Before anything else, call log_query. If the user's message is {word_limit} "
        "words or fewer, pass it verbatim with is_summary=false. If it is longer, pass a "
        f"faithful summary of at most {word_limit} words with is_summary=true and "
        "original_word_count set to your estimate of the message's length. "
        "It returns a turn_id. "
        "2) After you have finished your answer, call log_response with that turn_id, "
        "applying the same rule to your answer."
    )


def create_server(settings: Settings | None = None) -> MCPServer:
    """Create a fully configured server. Tests pass their own ``settings``."""
    settings = settings or Settings.from_env()

    repository = JsonlAuditRepository(settings.log_file)
    service = AuditService(repository, word_limit=settings.word_limit)
    identity_service = IdentityService(identity_settings)
    
    identity = identity_service.validate_token(access_token)
    
    print(identity)
    mcp = MCPServer(
        settings.server_name,
        version=__version__,
        instructions=build_instructions(settings.word_limit),
    )
    
    if not identity: 
        register_audit_tools(mcp, service)

    logger.info("Audit log: %s", repository.path)
    return mcp
