"""The append-only SQLite store.

Every write is an INSERT. Triggers make that structural rather than a
convention, so a future code path cannot quietly update history. See
docs/data-model.md and docs/decisions/0001-sqlite-over-duckdb.md.
"""

from __future__ import annotations

import json
import platform
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from squeegee import __version__
from squeegee.stages import Stage

TABLES = (
    "runs",
    "run_events",
    "stage_versions",
    "run_stages",
    "records",
    "record_events",
)

# events are buffered so that a ten thousand record run does not pay one
# transaction per stage per record
BATCH_SIZE = 1_000

_SCHEMA = Path(__file__).with_name("schema.sql")


class Store:
    """Write side of the run history."""

    def __init__(self, path: Path) -> None:
        """Open, and create if necessary, the database at ``path``."""
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._connection = sqlite3.connect(path)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        # NORMAL is the usual companion to WAL: a commit no longer waits on fsync,
        # which is the difference between a five second run and a fifteen second one.
        # The exposure is losing the most recent commits to a power cut, never to a
        # crash of squeegee itself, and this is a debugging record, not a ledger.
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._connection.executescript(_SCHEMA.read_text(encoding="utf-8"))
        self._connection.executescript(_append_only_triggers())
        self._connection.commit()
        self._pending: list[tuple[Any, ...]] = []
        self._closed = False

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def start_run(
        self,
        *,
        script_path: Path,
        script_sha256: str,
        input_path: Path,
        output_path: Path | None,
        options: dict[str, Any],
    ) -> int:
        """Insert the run row and its started event, and return the run id."""
        cursor = self._connection.execute(
            "INSERT INTO runs (started_at, script_path, script_sha256, input_path, "
            "output_path, squeegee_version, python_version, options_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                _now(),
                str(script_path),
                script_sha256,
                str(input_path),
                None if output_path is None else str(output_path),
                __version__,
                platform.python_version(),
                json.dumps(options, default=repr),
            ),
        )
        run_id = _row_id(cursor)
        self.add_run_event(run_id, "started")
        return run_id

    def add_run_event(self, run_id: int, kind: str, detail: dict[str, Any] | None = None) -> None:
        """Record a lifecycle event: started, finished, failed, or aborted."""
        self.flush()
        self._connection.execute(
            "INSERT INTO run_events (run_id, at, kind, detail_json) VALUES (?, ?, ?, ?)",
            (run_id, _now(), kind, None if detail is None else json.dumps(detail, default=repr)),
        )
        self._connection.commit()

    def register_stage(self, run_id: int, position: int, stage: Stage) -> int:
        """Attach a stage to a run at ``position`` and return the run_stage id.

        The stage version is reused when its name and source hash already exist,
        so an unedited stage resolves to one row across every run that used it.
        """
        self._connection.execute(
            "INSERT OR IGNORE INTO stage_versions "
            "(name, source_sha256, source_text, description, input_type, output_type, "
            "first_seen_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                stage.name,
                stage.source_sha256,
                stage.source_text,
                stage.description,
                stage.input_type,
                stage.output_type,
                _now(),
            ),
        )
        version_id = self._connection.execute(
            "SELECT id FROM stage_versions WHERE name = ? AND source_sha256 = ?",
            (stage.name, stage.source_sha256),
        ).fetchone()[0]
        cursor = self._connection.execute(
            "INSERT INTO run_stages (run_id, stage_version_id, position) VALUES (?, ?, ?)",
            (run_id, version_id, position),
        )
        self._connection.commit()
        return _row_id(cursor)

    def add_record(self, run_id: int, record_index: int, source: Any) -> int:
        """Store a record as it was read, and return its id.

        Buffered events are deliberately not flushed here: they already carry the
        record id they belong to, and flushing per record would commit once per
        record and undo the batching entirely.
        """
        cursor = self._connection.execute(
            "INSERT INTO records (run_id, record_index, source_json) VALUES (?, ?, ?)",
            (run_id, record_index, to_json(source)),
        )
        return _row_id(cursor)

    def add_record_event(
        self,
        *,
        record_id: int,
        run_stage_id: int,
        status: str,
        record_input: Any,
        record_output: Any = None,
        error_type: str | None = None,
        error_message: str | None = None,
        error_traceback: str | None = None,
        duration_us: int,
    ) -> None:
        """Buffer one stage's outcome for one record."""
        self._pending.append(
            (
                record_id,
                run_stage_id,
                _now(),
                status,
                to_json(record_input),
                None if record_output is None else to_json(record_output),
                error_type,
                error_message,
                error_traceback,
                duration_us,
            )
        )
        if len(self._pending) >= BATCH_SIZE:
            self.flush()

    def flush(self) -> None:
        """Write buffered record events."""
        if not self._pending:
            return
        self._connection.executemany(
            "INSERT INTO record_events (record_id, run_stage_id, at, status, input_json, "
            "output_json, error_type, error_message, error_traceback, duration_us) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            self._pending,
        )
        self._connection.commit()
        self._pending.clear()

    def close(self) -> None:
        """Flush anything buffered, commit, and close the connection.

        Records are inserted inside the transaction that the next flush commits,
        so closing without committing would roll the most recent ones back.
        """
        if self._closed:
            return
        self.flush()
        self._connection.commit()
        self._connection.close()
        self._closed = True


def to_json(value: Any) -> str:
    """Serialize a record value, keeping observability over fidelity.

    A value the JSON encoder refuses is stored as its repr inside a marker
    object, because losing the event entirely is worse than losing the exact
    value.
    """
    return json.dumps(value, default=_marker)


def _marker(value: Any) -> dict[str, str]:
    return {"__squeegee_unserializable__": repr(value)}


def _append_only_triggers() -> str:
    return "\n".join(
        f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action} BEFORE {action.upper()} ON {table} "
        f"BEGIN SELECT RAISE(ABORT, 'squeegee tables are append-only'); END;"
        for table in TABLES
        for action in ("update", "delete")
    )


def _row_id(cursor: sqlite3.Cursor) -> int:
    inserted = cursor.lastrowid
    if inserted is None:  # pragma: no cover - sqlite3 always sets this for an INSERT
        raise RuntimeError("sqlite did not report the inserted row id")
    return inserted


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
