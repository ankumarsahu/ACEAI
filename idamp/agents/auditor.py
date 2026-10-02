from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Iterator

from idamp.core.config import settings


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    settings.ensure_directories()
    connection = sqlite3.connect(settings.audit_db, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY, business_intent TEXT NOT NULL,
                started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS stage_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                stage TEXT NOT NULL, status TEXT NOT NULL, rows_out INTEGER,
                quality_score REAL, error_message TEXT, started_at TEXT NOT NULL,
                ended_at TEXT, FOREIGN KEY(run_id) REFERENCES runs(run_id)
            );
            """
        )
        with connection:
            yield connection
    finally:
        connection.close()


def ensure_run(run_id: str, intent: str) -> None:
    with _connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO runs(run_id,business_intent,started_at,status) VALUES(?,?,?,?)",
            (run_id, intent, datetime.now(UTC).isoformat(), "running"),
        )


def record_stage(run_id: str, stage: str, status: str, rows_out: int | None = None, quality: float | None = None, error: str | None = None, started_at: str | None = None) -> None:
    ended = datetime.now(UTC).isoformat()
    started = started_at or ended
    with _connect() as connection:
        connection.execute(
            "INSERT INTO stage_events(run_id,stage,status,rows_out,quality_score,error_message,started_at,ended_at) VALUES(?,?,?,?,?,?,?,?)",
            (run_id, stage, status, rows_out, quality, error, started, ended),
        )
        if stage == "report" or status == "failed":
            connection.execute("UPDATE runs SET status=?, finished_at=? WHERE run_id=?", ("completed" if status == "completed" else "failed", ended, run_id))


def get_stage_events(run_id: str) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute("SELECT * FROM stage_events WHERE run_id=? ORDER BY event_id", (run_id,)).fetchall()
    return [dict(row) for row in rows]


def get_recent_runs(n: int = 5) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (max(1, n),)).fetchall()
    return [dict(row) for row in rows]