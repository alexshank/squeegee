"""Read side of the store.

Only what the CLI needs for now; the endpoints of docs/api.md land with the
HTTP server. Every function opens the database read-only and returns plain
dictionaries, so nothing here can write and nothing here knows about HTTP.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from squeegee.errors import SqueegeeError

_RUN_COUNTS = """
SELECT
    (SELECT COUNT(*) FROM records WHERE run_id = :run_id) AS records_in,
    (SELECT COUNT(*) FROM record_events e JOIN run_stages rs ON rs.id = e.run_stage_id
      WHERE rs.run_id = :run_id AND e.status = 'dropped') AS records_dropped,
    (SELECT COUNT(*) FROM record_events e JOIN run_stages rs ON rs.id = e.run_stage_id
      WHERE rs.run_id = :run_id AND e.status = 'error') AS records_errored
"""


def list_runs(database_path: Path, limit: int = 20) -> list[dict[str, Any]]:
    """Return the most recent runs, newest first."""
    with _read_only(database_path) as connection:
        runs = connection.execute(
            "SELECT r.id AS run_id, r.script_path, r.input_path, r.output_path, "
            "s.started_at, s.ended_at, s.status "
            "FROM runs r JOIN run_status s ON s.run_id = r.id ORDER BY r.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [{**dict(run), **_counts(connection, run["run_id"])} for run in runs]


def run_summary(database_path: Path, run_id: int) -> dict[str, Any]:
    """Return one run with its per-stage counts.

    Raises:
        SqueegeeError: No run has that id.
    """
    with _read_only(database_path) as connection:
        run = connection.execute(
            "SELECT r.id AS run_id, r.script_path, r.input_path, r.output_path, "
            "r.squeegee_version, r.python_version, r.options_json, "
            "s.started_at, s.ended_at, s.status "
            "FROM runs r JOIN run_status s ON s.run_id = r.id WHERE r.id = ?",
            (run_id,),
        ).fetchone()
        if run is None:
            raise SqueegeeError(f"no run {run_id} in {database_path}")
        return {
            **dict(run),
            **_counts(connection, run_id),
            "stages": _stages(connection, run_id),
            "failure": _failure(connection, run_id),
        }


def _stages(connection: sqlite3.Connection, run_id: int) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            "SELECT rs.position, sv.name, sv.description, "
            "COUNT(e.id) AS records_in, "
            "SUM(e.status = 'ok') AS records_ok, "
            "SUM(e.status = 'dropped') AS records_dropped, "
            "SUM(e.status = 'error') AS records_errored, "
            "COALESCE(SUM(e.duration_us), 0) AS duration_us_total "
            "FROM run_stages rs "
            "JOIN stage_versions sv ON sv.id = rs.stage_version_id "
            "LEFT JOIN record_events e ON e.run_stage_id = rs.id "
            "WHERE rs.run_id = ? GROUP BY rs.id ORDER BY rs.position",
            (run_id,),
        )
    ]


def _failure(connection: sqlite3.Connection, run_id: int) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT rs.position AS stage_position, sv.name AS stage_name, "
        "rec.record_index, e.error_type, e.error_message "
        "FROM record_events e "
        "JOIN run_stages rs ON rs.id = e.run_stage_id "
        "JOIN stage_versions sv ON sv.id = rs.stage_version_id "
        "JOIN records rec ON rec.id = e.record_id "
        "WHERE rs.run_id = ? AND e.status = 'error' ORDER BY e.id DESC LIMIT 1",
        (run_id,),
    ).fetchone()
    status = connection.execute(
        "SELECT status FROM run_status WHERE run_id = ?", (run_id,)
    ).fetchone()[0]
    return dict(row) if row is not None and status == "failed" else None


def _counts(connection: sqlite3.Connection, run_id: int) -> dict[str, Any]:
    counts = dict(connection.execute(_RUN_COUNTS, {"run_id": run_id}).fetchone())
    counts["records_out"] = connection.execute(
        "SELECT COUNT(*) FROM record_events e "
        "JOIN run_stages rs ON rs.id = e.run_stage_id "
        "WHERE rs.run_id = ? AND e.status = 'ok' "
        "AND rs.position = (SELECT MAX(position) FROM run_stages WHERE run_id = ?)",
        (run_id, run_id),
    ).fetchone()[0]
    return counts


def _read_only(database_path: Path) -> sqlite3.Connection:
    if not database_path.is_file():
        raise SqueegeeError(f"no squeegee database at {database_path}")
    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection
