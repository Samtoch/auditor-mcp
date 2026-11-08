"""Entry point: ``uv run auditor-mcp`` or ``python -m app``."""

import logging

from app import __version__
from app.config import Settings
from app.logging_setup import configure_logging
from app.mcp.server import create_server


def main() -> None:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    logging.getLogger(__name__).info("auditor-mcp %s starting (stdio)", __version__)
    create_server(settings).run(transport="stdio")


if __name__ == "__main__":
    main()
