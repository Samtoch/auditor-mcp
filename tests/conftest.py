from pathlib import Path

import pytest

from auditor_mcp.config import Settings
from auditor_mcp.services import AuditService
from auditor_mcp.storage import JsonlAuditRepository


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(log_dir=tmp_path / "logs", word_limit=5)


@pytest.fixture
def repository(settings: Settings) -> JsonlAuditRepository:
    return JsonlAuditRepository(settings.log_file)


@pytest.fixture
def service(repository: JsonlAuditRepository, settings: Settings) -> AuditService:
    ids = iter(f"turn{n}" for n in range(1, 1000))
    return AuditService(
        repository,
        word_limit=settings.word_limit,
        clock=lambda: "2026-10-10T00:00:00+00:00",
        id_factory=lambda: next(ids),
    )
