"""Read side of the store: one function per endpoint in docs/api.md.

Every function opens the database read-only and returns plain dictionaries,
so nothing here can write and nothing here knows about HTTP. Statistics are
SQLite aggregates over the stored JSON rather than anything loaded into
memory.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from squeegee import __version__
from squeegee.errors import SqueegeeError

# the only value ever interpolated into a statement below is `column`, which is
# always one of two literals chosen in this module, never anything from a request
MAX_PAGE = 500
DEFAULT_PAGE = 50

Row = dict[str, Any]

_FINAL_STATUS = """
WITH final AS (
    SELECT r.id AS record_id, r.record_index,
           (SELECT e.status FROM record_events e
             WHERE e.record_id = r.id ORDER BY e.id DESC LIMIT 1) AS status
    FROM records r WHERE r.run_id = :run_id
)
"""


def meta(database_path: Path) -> Row:
    """Server and database identity, for the UI header."""
    with _read_only(database_path) as connection:
        return {
            "squeegee_version": __version__,
            "database_path": str(database_path),
            "run_count": connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0],
        }


def list_runs(
    database_path: Path,
    limit: int = DEFAULT_PAGE,
    cursor: str | None = None,
    script: str | None = None,
) -> Row:
    """Return runs newest first, paginated."""
    with _read_only(database_path) as connection:
        runs = connection.execute(
            "SELECT r.id AS run_id, r.script_path, r.input_path, r.output_path, "
            "s.started_at, s.ended_at, s.status "
            "FROM runs r JOIN run_status s ON s.run_id = r.id "
            "WHERE (:cursor IS NULL OR r.id < :cursor) "
            "AND (:script IS NULL OR r.script_path LIKE '%' || :script || '%') "
            "ORDER BY r.id DESC LIMIT :limit",
            {"cursor": cursor, "script": script, "limit": _page(limit) + 1},
        ).fetchall()
        items = [
            {
                **dict(run),
                **_counts(connection, run["run_id"]),
                "duration_us": _duration_us(run["started_at"], run["ended_at"]),
            }
            for run in runs[: _page(limit)]
        ]
        return _page_of(items, runs, limit, key="run_id")


def run_summary(database_path: Path, run_id: int) -> Row:
    """One run: metadata, totals, its stages, and its failure if it has one.

    Raises:
        SqueegeeError: No run has that id.
    """
    with _read_only(database_path) as connection:
        run = connection.execute(
            "SELECT r.id AS run_id, r.script_path, r.script_sha256, r.input_path, r.output_path, "
            "r.squeegee_version, r.python_version, r.options_json, "
            "s.started_at, s.ended_at, s.status "
            "FROM runs r JOIN run_status s ON s.run_id = r.id WHERE r.id = ?",
            (run_id,),
        ).fetchone()
        if run is None:
            raise SqueegeeError(f"no run {run_id} in {database_path}")
        summary = dict(run)
        options = json.loads(summary.pop("options_json"))
        return {
            **summary,
            "options": options,
            "duration_us": _duration_us(run["started_at"], run["ended_at"]),
            **_counts(connection, run_id),
            "stages": _stage_rows(connection, run_id),
            "failure": _failure(connection, run_id),
        }


def stage_detail(database_path: Path, run_id: int, position: int) -> Row:
    """One stage, including the source text the UI highlights."""
    with _read_only(database_path) as connection:
        stage = connection.execute(
            "SELECT rs.id AS run_stage_id, rs.position, sv.id AS stage_version_id, sv.name, "
            "sv.description, sv.input_type, sv.output_type, sv.source_text, sv.source_sha256, "
            "sv.first_seen_at "
            "FROM run_stages rs JOIN stage_versions sv ON sv.id = rs.stage_version_id "
            "WHERE rs.run_id = ? AND rs.position = ?",
            (run_id, position),
        ).fetchone()
        _require(stage, f"run {run_id} has no stage at position {position}")
        detail = dict(stage)
        detail["source_language"] = "python"
        detail["also_used_by_runs"] = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT run_id FROM run_stages "
                "WHERE stage_version_id = ? AND run_id != ? ORDER BY run_id",
                (stage["stage_version_id"], run_id),
            )
        ]
        detail["counts"] = _stage_counts(connection, stage["run_stage_id"])
        return detail


def stage_records(
    database_path: Path,
    run_id: int,
    position: int,
    status: str | None = None,
    search: str | None = None,
    limit: int = DEFAULT_PAGE,
    cursor: str | None = None,
) -> Row:
    """Paginated record events for one stage."""
    _check_status(status)
    with _read_only(database_path) as connection:
        run_stage_id = _run_stage_id(connection, run_id, position)
        events = connection.execute(
            "SELECT e.id, r.record_index, e.status, e.input_json, e.output_json, "
            "e.error_type, e.error_message, e.duration_us "
            "FROM record_events e JOIN records r ON r.id = e.record_id "
            "WHERE e.run_stage_id = :run_stage_id "
            "AND (:status IS NULL OR e.status = :status) "
            "AND (:cursor IS NULL OR e.id > :cursor) "
            "AND (:search IS NULL OR e.input_json LIKE '%' || :search || '%' "
            "     OR e.output_json LIKE '%' || :search || '%') "
            "ORDER BY e.id LIMIT :limit",
            {
                "run_stage_id": run_stage_id,
                "status": status,
                "cursor": cursor,
                "search": search,
                "limit": _page(limit) + 1,
            },
        ).fetchall()
        items = [_event_row(event) for event in events[: _page(limit)]]
        return _page_of(items, events, limit, key="id", rows=events)


def record_trace(
    database_path: Path, run_id: int, record_index: int, status: str | None = None
) -> Row:
    """One record's whole journey, plus where to step next."""
    _check_status(status)
    with _read_only(database_path) as connection:
        record = connection.execute(
            "SELECT id, source_json FROM records WHERE run_id = ? AND record_index = ?",
            (run_id, record_index),
        ).fetchone()
        _require(record, f"run {run_id} has no record {record_index}")
        events = [
            _trace_event(event)
            for event in connection.execute(
                "SELECT rs.position, sv.name AS stage_name, e.status, e.input_json, "
                "e.output_json, e.error_type, e.error_message, e.duration_us "
                "FROM record_events e "
                "JOIN run_stages rs ON rs.id = e.run_stage_id "
                "JOIN stage_versions sv ON sv.id = rs.stage_version_id "
                "WHERE e.record_id = ? ORDER BY rs.position",
                (record["id"],),
            )
        ]
        neighbours = _neighbours(connection, run_id, record_index, status)
        return {
            "record_index": record_index,
            "source": json.loads(record["source_json"]),
            "final_status": events[-1]["status"] if events else None,
            "events": events,
            **neighbours,
        }


def stage_fields(database_path: Path, run_id: int, position: int) -> Row:
    """Per-field statistics over the stage's successful outputs."""
    with _read_only(database_path) as connection:
        run_stage_id = _run_stage_id(connection, run_id, position)
        considered = connection.execute(
            "SELECT COUNT(*) FROM record_events WHERE run_stage_id = ? AND status = 'ok'",
            (run_stage_id,),
        ).fetchone()[0]
        return {
            "records_considered": considered,
            "items": [
                _field_stats(connection, run_stage_id, field, considered)
                for field in _fields_of(connection, run_stage_id)
            ],
        }


def field_detail(
    database_path: Path,
    run_id: int,
    position: int,
    field: str,
    bins: int = 20,
    top: int = 20,
) -> Row:
    """One field after the stage, and the same field before it."""
    if not 5 <= bins <= 50:
        raise SqueegeeError("bins must be between 5 and 50")
    if not 1 <= top <= 100:
        raise SqueegeeError("top must be between 1 and 100")
    with _read_only(database_path) as connection:
        run_stage_id = _run_stage_id(connection, run_id, position)
        considered = connection.execute(
            "SELECT COUNT(*) FROM record_events WHERE run_stage_id = ? AND status = 'ok'",
            (run_stage_id,),
        ).fetchone()[0]
        after = _field_stats(connection, run_stage_id, field, considered)
        if after["non_null_count"] == 0 and field not in _fields_of(connection, run_stage_id):
            raise SqueegeeError(f"stage {position} of run {run_id} has no field {field!r}")
        return {
            "field": field,
            "inferred_type": after["inferred_type"],
            "after": _distribution(
                connection, run_stage_id, field, after, bins, top, "output_json"
            ),
            "before": _before(connection, run_stage_id, field, considered, bins, top),
        }


def _before(
    connection: sqlite3.Connection,
    run_stage_id: int,
    field: str,
    considered: int,
    bins: int,
    top: int,
) -> Row | None:
    stats = _field_stats(connection, run_stage_id, field, considered, column="input_json")
    if stats["non_null_count"] == 0:
        # the field did not exist before this stage, which is itself worth knowing
        return None
    return _distribution(connection, run_stage_id, field, stats, bins, top, "input_json")


def _distribution(
    connection: sqlite3.Connection,
    run_stage_id: int,
    field: str,
    stats: Row,
    bins: int,
    top: int,
    column: str,
) -> Row:
    numeric = stats["inferred_type"] == "number"
    return {
        "stats": stats,
        "histogram": _histogram(connection, run_stage_id, field, stats, bins, column)
        if numeric
        else None,
        "top_values": None
        if numeric
        else _top_values(connection, run_stage_id, field, top, column),
    }


def _histogram(
    connection: sqlite3.Connection,
    run_stage_id: int,
    field: str,
    stats: Row,
    bins: int,
    column: str,
) -> list[Row]:
    low, high = stats["min"], stats["max"]
    # unreachable while callers gate on inferred_type == "number", which implies a value
    if low is None or high is None:  # pragma: no cover
        return []
    width = (high - low) / bins or 1
    counts = dict(
        connection.execute(
            f"SELECT MIN(CAST((json_extract({column}, :path) - :low) / :width AS INTEGER), "
            f":last) AS bucket, COUNT(*) FROM record_events "
            f"WHERE run_stage_id = :run_stage_id AND status = 'ok' "
            f"AND json_extract({column}, :path) IS NOT NULL GROUP BY bucket",
            {
                "path": _path(field),
                "low": low,
                "width": width,
                "last": bins - 1,
                "run_stage_id": run_stage_id,
            },
        ).fetchall()
    )
    return [
        {
            "lower": low + width * bucket,
            "upper": low + width * (bucket + 1),
            "count": counts.get(bucket, 0),
        }
        for bucket in range(bins)
    ]


def _top_values(
    connection: sqlite3.Connection, run_stage_id: int, field: str, top: int, column: str
) -> list[Row]:
    return [
        {"value": value, "count": count}
        for value, count in connection.execute(
            f"SELECT json_extract({column}, :path) AS value, COUNT(*) AS occurrences "
            f"FROM record_events WHERE run_stage_id = :run_stage_id AND status = 'ok' "
            f"AND json_extract({column}, :path) IS NOT NULL "
            f"GROUP BY value ORDER BY occurrences DESC, value LIMIT :top",
            {"path": _path(field), "run_stage_id": run_stage_id, "top": top},
        ).fetchall()
    ]


def _fields_of(connection: sqlite3.Connection, run_stage_id: int) -> list[str]:
    return [
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT each.key FROM record_events, "
            "json_each(record_events.output_json) each "
            "WHERE run_stage_id = ? AND status = 'ok' ORDER BY each.key",
            (run_stage_id,),
        )
    ]


def _field_stats(
    connection: sqlite3.Connection,
    run_stage_id: int,
    field: str,
    considered: int,
    column: str = "output_json",
) -> Row:
    path = _path(field)
    row = connection.execute(
        f"SELECT COUNT(json_extract({column}, :path)) AS non_null_count, "
        f"COUNT(DISTINCT json_extract({column}, :path)) AS distinct_count, "
        f"COUNT(DISTINCT json_type({column}, :path)) AS type_count, "
        f"MIN(json_type({column}, :path)) AS a_type "
        f"FROM record_events WHERE run_stage_id = :run_stage_id AND status = 'ok'",
        {"path": path, "run_stage_id": run_stage_id},
    ).fetchone()
    stats: Row = {
        "field": field,
        "inferred_type": _inferred_type(row["type_count"], row["a_type"]),
        "non_null_count": row["non_null_count"],
        "null_count": considered - row["non_null_count"],
        "distinct_count": row["distinct_count"],
        "min": None,
        "max": None,
        "mean": None,
        "median": None,
        "sum": None,
    }
    if stats["inferred_type"] == "number":
        numbers = connection.execute(
            f"SELECT MIN(v), MAX(v), AVG(v), SUM(v) FROM "
            f"(SELECT json_extract({column}, :path) AS v FROM record_events "
            f"WHERE run_stage_id = :run_stage_id AND status = 'ok' AND v IS NOT NULL)",
            {"path": path, "run_stage_id": run_stage_id},
        ).fetchone()
        stats |= {
            "min": numbers[0],
            "max": numbers[1],
            "mean": numbers[2],
            "sum": numbers[3],
            "median": _median(connection, run_stage_id, path, column, row["non_null_count"]),
        }
    return stats


def _median(
    connection: sqlite3.Connection, run_stage_id: int, path: str, column: str, count: int
) -> float | None:
    # likewise unreachable: a numeric field has at least one number to sit in the middle
    if count == 0:  # pragma: no cover
        return None
    # hand-rolled, because SQLite has no percentile function and the store is not DuckDB
    middle = connection.execute(
        f"SELECT json_extract({column}, :path) AS v FROM record_events "
        f"WHERE run_stage_id = :run_stage_id AND status = 'ok' AND v IS NOT NULL "
        f"ORDER BY v LIMIT 1 OFFSET :offset",
        {"path": path, "run_stage_id": run_stage_id, "offset": (count - 1) // 2},
    ).fetchone()
    return float(middle[0]) if middle is not None else None


def _inferred_type(type_count: int, a_type: str | None) -> str:
    if a_type is None:
        return "null"
    if type_count > 1:
        return "mixed"
    return {
        "integer": "number",
        "real": "number",
        "text": "string",
        "true": "boolean",
        "false": "boolean",
        "object": "object",
        "array": "array",
    }.get(a_type, a_type)


def _stage_rows(connection: sqlite3.Connection, run_id: int) -> list[Row]:
    stages = connection.execute(
        "SELECT rs.id AS run_stage_id, rs.position, sv.id AS stage_version_id, sv.name, "
        "sv.description FROM run_stages rs JOIN stage_versions sv ON sv.id = rs.stage_version_id "
        "WHERE rs.run_id = ? ORDER BY rs.position",
        (run_id,),
    ).fetchall()
    return [{**dict(stage), **_stage_counts(connection, stage["run_stage_id"])} for stage in stages]


def _stage_counts(connection: sqlite3.Connection, run_stage_id: int) -> Row:
    counts = connection.execute(
        "SELECT COUNT(*) AS records_in, "
        "COALESCE(SUM(status = 'ok'), 0) AS records_ok, "
        "COALESCE(SUM(status = 'dropped'), 0) AS records_dropped, "
        "COALESCE(SUM(status = 'error'), 0) AS records_errored, "
        "COALESCE(SUM(duration_us), 0) AS duration_us_total "
        "FROM record_events WHERE run_stage_id = ?",
        (run_stage_id,),
    ).fetchone()
    return {
        **dict(counts),
        "duration_us_median": _duration_quantile(connection, run_stage_id, 0.5),
        "duration_us_p95": _duration_quantile(connection, run_stage_id, 0.95),
    }


def _duration_quantile(
    connection: sqlite3.Connection, run_stage_id: int, fraction: float
) -> int | None:
    count = connection.execute(
        "SELECT COUNT(*) FROM record_events WHERE run_stage_id = ?", (run_stage_id,)
    ).fetchone()[0]
    if count == 0:
        return None
    row = connection.execute(
        "SELECT duration_us FROM record_events WHERE run_stage_id = ? "
        "ORDER BY duration_us LIMIT 1 OFFSET ?",
        (run_stage_id, min(int(count * fraction), count - 1)),
    ).fetchone()
    return int(row[0])


def _failure(connection: sqlite3.Connection, run_id: int) -> Row | None:
    status = connection.execute(
        "SELECT status FROM run_status WHERE run_id = ?", (run_id,)
    ).fetchone()[0]
    if status != "failed":
        return None
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
    return dict(row) if row is not None else None


def _neighbours(
    connection: sqlite3.Connection, run_id: int, record_index: int, status: str | None
) -> Row:
    parameters = {"run_id": run_id, "record_index": record_index, "status": status}
    previous = connection.execute(
        _FINAL_STATUS + "SELECT MAX(record_index) FROM final "
        "WHERE record_index < :record_index AND (:status IS NULL OR status = :status)",
        parameters,
    ).fetchone()[0]
    following = connection.execute(
        _FINAL_STATUS + "SELECT MIN(record_index) FROM final "
        "WHERE record_index > :record_index AND (:status IS NULL OR status = :status)",
        parameters,
    ).fetchone()[0]
    return {"previous_record_index": previous, "next_record_index": following}


def _event_row(event: sqlite3.Row) -> Row:
    return {
        "record_index": event["record_index"],
        "status": event["status"],
        "input": json.loads(event["input_json"]),
        "output": None if event["output_json"] is None else json.loads(event["output_json"]),
        "error_type": event["error_type"],
        "error_message": event["error_message"],
        "duration_us": event["duration_us"],
    }


def _trace_event(event: sqlite3.Row) -> Row:
    stage_input = json.loads(event["input_json"])
    stage_output = None if event["output_json"] is None else json.loads(event["output_json"])
    return {
        "position": event["position"],
        "stage_name": event["stage_name"],
        "status": event["status"],
        "input": stage_input,
        "output": stage_output,
        "changed_fields": _changed_fields(stage_input, stage_output),
        "error_type": event["error_type"],
        "error_message": event["error_message"],
        "duration_us": event["duration_us"],
    }


def _changed_fields(stage_input: Any, stage_output: Any) -> list[str]:
    if not isinstance(stage_input, dict) or not isinstance(stage_output, dict):
        return []
    return sorted(
        key
        for key in stage_input.keys() | stage_output.keys()
        if stage_input.get(key) != stage_output.get(key)
    )


def _counts(connection: sqlite3.Connection, run_id: int) -> Row:
    counts = dict(
        connection.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM records WHERE run_id = :run_id) AS records_in, "
            "(SELECT COUNT(*) FROM record_events e JOIN run_stages rs ON rs.id = e.run_stage_id "
            "  WHERE rs.run_id = :run_id AND e.status = 'dropped') AS records_dropped, "
            "(SELECT COUNT(*) FROM record_events e JOIN run_stages rs ON rs.id = e.run_stage_id "
            "  WHERE rs.run_id = :run_id AND e.status = 'error') AS records_errored, "
            "(SELECT COUNT(*) FROM run_stages WHERE run_id = :run_id) AS stage_count",
            {"run_id": run_id},
        ).fetchone()
    )
    counts["records_out"] = connection.execute(
        "SELECT COUNT(*) FROM record_events e JOIN run_stages rs ON rs.id = e.run_stage_id "
        "WHERE rs.run_id = ? AND e.status = 'ok' "
        "AND rs.position = (SELECT MAX(position) FROM run_stages WHERE run_id = ?)",
        (run_id, run_id),
    ).fetchone()[0]
    return counts


def _run_stage_id(connection: sqlite3.Connection, run_id: int, position: int) -> int:
    row = connection.execute(
        "SELECT id FROM run_stages WHERE run_id = ? AND position = ?", (run_id, position)
    ).fetchone()
    _require(row, f"run {run_id} has no stage at position {position}")
    return int(row[0])


def _page_of(
    items: list[Row],
    fetched: list[sqlite3.Row],
    limit: int,
    key: str,
    rows: list[sqlite3.Row] | None = None,
) -> Row:
    has_more = len(fetched) > _page(limit)
    cursor_source = rows or fetched
    return {
        "items": items,
        "next_cursor": str(cursor_source[_page(limit) - 1][key]) if has_more else None,
        "has_more": has_more,
    }


def _page(limit: int) -> int:
    if limit < 1:
        raise SqueegeeError("limit must be at least 1")
    return min(limit, MAX_PAGE)


def _path(field: str) -> str:
    return '$."' + field.replace('"', '\\"') + '"'


def _check_status(status: str | None) -> None:
    if status is not None and status not in ("ok", "dropped", "error"):
        raise SqueegeeError(f"status must be ok, dropped, or error, not {status!r}")


def _require(row: object | None, message: str) -> None:
    if row is None:
        raise SqueegeeError(message)


def _duration_us(started_at: str, ended_at: str | None) -> int | None:
    if ended_at is None:
        return None
    from datetime import datetime

    started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    ended = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
    return int((ended - started).total_seconds() * 1_000_000)


def _read_only(database_path: Path) -> sqlite3.Connection:
    if not database_path.is_file():
        raise SqueegeeError(f"no squeegee database at {database_path}")
    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection
