"""Runtime settings, read from environment variables with sensible defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_PREFIX = "AUDITOR_"
DEFAULT_WORD_LIMIT = 100
DEFAULT_LOG_LEVEL = "INFO"


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuration for one server instance.

    Attributes:
        server_name: Name reported to MCP clients.
        log_dir: Folder that holds the audit log.
        log_file_name: Name of the JSONL audit file inside ``log_dir``.
        word_limit: Maximum number of words stored per query or response.
        log_level: Level for diagnostic logging (written to stderr).
    """

    server_name: str = "auditor"
    log_dir: Path = Path("logs")
    log_file_name: str = "audit.jsonl"
    word_limit: int = DEFAULT_WORD_LIMIT
    log_level: str = DEFAULT_LOG_LEVEL

    def __post_init__(self) -> None:
        if self.word_limit < 1:
            raise ValueError(f"word_limit must be at least 1, got {self.word_limit}")

    @property
    def log_file(self) -> Path:
        return self.log_dir / self.log_file_name

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from ``AUDITOR_*`` environment variables.

        ``AUDITOR_LOG_DIR`` defaults to ``./logs`` relative to the working directory.
        Claude Desktop launches the server with ``uv --directory <project>``, so that
        resolves to the project folder.
        """
        env = os.environ
        return cls(
            log_dir=Path(env.get(f"{ENV_PREFIX}LOG_DIR", Path.cwd() / "logs")).resolve(),
            word_limit=int(env.get(f"{ENV_PREFIX}WORD_LIMIT", DEFAULT_WORD_LIMIT)),
            log_level=env.get(f"{ENV_PREFIX}LOG_LEVEL", DEFAULT_LOG_LEVEL).upper(),
        )
