"""Reusable PostgreSQL connection with serialized transaction sessions."""

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from threading import Lock

import psycopg2
from dotenv import dotenv_values
from psycopg2.extensions import connection, cursor


class PostgresClient:
    """Connect lazily; use one session per unit of work.

    Sessions are serialized. Do not nest sessions on the same client.
    Use a pool when concurrent database sessions are required.
    """

    def __init__(self, env_file: str | Path = ".env.local") -> None:
        # Environment overrides local settings without modifying os.environ.
        config = {**dotenv_values(env_file), **os.environ}
        self._dsn = config.get("DATABASE_URL")
        if not self._dsn:
            raise ValueError("DATABASE_URL must be configured in .env.local or the environment.")
        self._options = {
            key: config[name]
            for key, name in (("user", "PGUSER"), ("password", "PGPASSWORD"))
            if config.get(name)
        }
        self._connection: connection | None = None
        self._lock = Lock()

    def _ensure_connection(self) -> connection:
        """Check the idle connection before starting a new transaction."""
        conn = self._connection
        if conn is not None and not conn.closed:
            try:
                with conn, conn.cursor() as probe:
                    probe.execute("SELECT 1")
                return conn
            except (psycopg2.InterfaceError, psycopg2.OperationalError):
                conn.close()
        self._connection = None
        self._connection = psycopg2.connect(self._dsn, connect_timeout=10, **self._options)
        return self._connection

    @contextmanager
    def session(self) -> Generator[cursor, None, None]:
        """Commit on success or roll back on failure; never replay a transaction."""
        with self._lock:
            conn = self._ensure_connection()
            with conn, conn.cursor() as session_cursor:
                yield session_cursor

    def close(self) -> None:
        """Release the connection. A later session will reconnect."""
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
