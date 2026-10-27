"""Connection lifecycle checks without accessing a real database."""

from unittest.mock import MagicMock, patch

import psycopg2
import pytest

from auditor_mcp.storage.postgres import PostgresClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    for name in ("DATABASE_URL", "PGUSER", "PGPASSWORD"):
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env.local"
    env_file.write_text("DATABASE_URL=postgresql://localhost/test\nPGUSER=test\nPGPASSWORD=secret\n")
    return PostgresClient(env_file)


def test_lazy_connection_and_reuse(client):
    conn = MagicMock(closed=0)
    with patch("auditor_mcp.storage.postgres.psycopg2.connect", return_value=conn) as connect:
        connect.assert_not_called()
        with client.session():
            pass
        with client.session():
            pass
        connect.assert_called_once_with(
            "postgresql://localhost/test", connect_timeout=10, user="test", password="secret"
        )
        conn.cursor.return_value.__enter__.return_value.execute.assert_called_once_with("SELECT 1")
        client.close()
        conn.close.assert_called_once()


@pytest.mark.parametrize("closed", [0, 1])
def test_reconnects_before_session(client, closed):
    stale = MagicMock(closed=closed)
    stale.cursor.side_effect = psycopg2.OperationalError("disconnected")
    client._connection = stale
    fresh = MagicMock(closed=0)
    with patch("auditor_mcp.storage.postgres.psycopg2.connect", return_value=fresh) as connect:
        with client.session():
            pass
        connect.assert_called_once()
        assert client._connection is fresh


def test_failed_session_propagates_without_retry(client):
    conn = MagicMock(closed=0)
    conn.__exit__.return_value = False
    with patch("auditor_mcp.storage.postgres.psycopg2.connect", return_value=conn) as connect:
        with pytest.raises(ValueError, match="failed"), client.session():
            raise ValueError("failed")
        assert conn.__exit__.call_args.args[0] is ValueError
        connect.assert_called_once()
