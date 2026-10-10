"""Entry point: ``uv run auditor-mcp`` or ``python -m auditor_mcp``."""

import logging

from auditor_mcp import __version__
from auditor_mcp.config import Settings
from auditor_mcp.logging_setup import configure_logging
from auditor_mcp.server import create_server


def main() -> None:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    logging.getLogger(__name__).info("auditor-mcp %s starting (stdio)", __version__)
    create_server(settings).run(transport="stdio")


if __name__ == "__main__":
    main()
