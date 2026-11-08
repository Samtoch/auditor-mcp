"""Diagnostic logging.

Everything goes to stderr: in a stdio MCP server, stdout carries the protocol,
and anything else written there corrupts it.
"""

import logging
import sys

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(stream=sys.stderr, level=level, format=LOG_FORMAT, force=True)
