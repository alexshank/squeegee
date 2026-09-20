"""Tests for the append-only SQLite store."""

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from squeegee.stages import Stage, clear_registry, registered_stages, stage
from squeegee.store import Store, to_json
from squeegee.store.sqlite import BATCH_SIZE, TABLES


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store(tmp_path / "nested" / "squeegee.db") as opened:
        yield opened


@pytest.fixture
def a_stage() -> Stage:
    clear_registry()

    @stage
    def parse_amount(record: dict[str, Any]) -> dict[str, Any]:
        """Convert the amount column to cents."""
        return record

    return registered_stages()[0]


def start(store: Store) -> int:
    return store.start_run(
        script_path=Path("clean_orders.py"),
        script_sha256="9f2c",
        input_path=Path("orders.csv"),
        output_path=Path("clean.csv"),
        options={"continue_on_error": False},
    )


def populate(store: Store, a_stage: Stage) -> None:
    """Write one row to every table, so an illegal statement has something to hit."""
    run_id = start(store)
    run_stage_id = store.register_stage(run_id, 0, a_stage)
    record_id = store.add_record(run_id, 0, {"id": "1"})
    store.add_record_event(
        record_id=record_id,
        run_stage_id=run_stage_id,
        status="ok",
        record_input={"id": "1"},
        record_output={"id": "1"},
        duration_us=38,
    )
    store.add_run_event(run_id, "finished", {"records_out": 1})


def query(store: Store, sql: str, *parameters: Any) -> list[tuple[Any, ...]]:
    store.flush()
    with sqlite3.connect(store.path) as connection:
        return connection.execute(sql, parameters).fetchall()


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("statement", ["UPDATE {table} SET id = id", "DELETE FROM {table}"])
def test_tables_reject_updates_and_deletes(
    store: Store, a_stage: Stage, table: str, statement: str
) -> None:
    populate(store, a_stage)
    # closed first: the store holds an open write transaction between batches, and a
    # second writer would otherwise sit waiting for the lock rather than hitting the trigger
    store.close()

    with sqlite3.connect(store.path) as connection, pytest.raises(sqlite3.IntegrityError) as raised:
        connection.execute(statement.format(table=table))

    assert "append-only" in str(raised.value)


def test_a_run_is_started_and_finished_through_events(store: Store) -> None:
    run_id = start(store)
    assert query(store, "SELECT status FROM run_status WHERE run_id = ?", run_id) == [("started",)]

    store.add_run_event(run_id, "finished", {"records_out": 3})

    status = query(store, "SELECT status, ended_at FROM run_status WHERE run_id = ?", run_id)[0]
    assert status[0] == "finished"
    assert status[1] is not None


def test_a_failed_run_keeps_its_failure_detail(store: Store) -> None:
    run_id = start(store)
    store.add_run_event(run_id, "failed", {"stage_name": "parse_amount", "record_index": 4471})

    detail = query(store, "SELECT detail_json FROM run_events WHERE kind = 'failed'")[0][0]
    assert json.loads(detail)["record_index"] == 4471


def test_an_unedited_stage_is_registered_once_across_runs(store: Store, a_stage: Stage) -> None:
    first_run, second_run = start(store), start(store)

    store.register_stage(first_run, 0, a_stage)
    store.register_stage(second_run, 0, a_stage)

    assert query(store, "SELECT COUNT(*) FROM stage_versions") == [(1,)]
    assert query(store, "SELECT COUNT(*) FROM run_stages") == [(2,)]


def test_an_edited_stage_keeps_the_older_source_readable(store: Store, a_stage: Stage) -> None:
    edited = Stage(
        name=a_stage.name,
        description=a_stage.description,
        func=a_stage.func,
        source_text="@stage\ndef parse_amount(record):\n    return record | {'edited': True}\n",
        source_sha256="different",
        input_type=None,
        output_type=None,
    )
    older_run, newer_run = start(store), start(store)

    store.register_stage(older_run, 0, a_stage)
    store.register_stage(newer_run, 0, edited)

    sources = query(
        store,
        "SELECT rs.run_id, sv.source_text FROM run_stages rs "
        "JOIN stage_versions sv ON sv.id = rs.stage_version_id ORDER BY rs.run_id",
    )
    assert sources[0][0] == older_run
    assert "edited" not in sources[0][1]
    assert "edited" in sources[1][1]


def test_annotations_are_stored_as_null_when_the_user_wrote_none(store: Store) -> None:
    clear_registry()

    @stage
    def bare(record):  # type: ignore[no-untyped-def] # a user script needs no annotations
        return record

    store.register_stage(start(store), 0, registered_stages()[0])

    assert query(store, "SELECT input_type, output_type FROM stage_versions") == [(None, None)]


def test_events_are_written_for_every_status(store: Store, a_stage: Stage) -> None:
    run_id = start(store)
    run_stage_id = store.register_stage(run_id, 0, a_stage)
    record_id = store.add_record(run_id, 0, {"id": "1"})

    store.add_record_event(
        record_id=record_id,
        run_stage_id=run_stage_id,
        status="ok",
        record_input={"id": "1"},
        record_output={"id": "1", "amount_cents": 2999},
        duration_us=38,
    )
    store.add_record_event(
        record_id=record_id,
        run_stage_id=run_stage_id,
        status="error",
        record_input={"id": "1"},
        error_type="ValueError",
        error_message="could not convert string to float: 'n/a'",
        error_traceback="Traceback...",
        duration_us=41,
    )

    events = query(store, "SELECT status, output_json, error_type FROM record_events ORDER BY id")
    assert [event[0] for event in events] == ["ok", "error"]
    assert json.loads(events[0][1])["amount_cents"] == 2999
    assert (events[1][1], events[1][2]) == (None, "ValueError")


def test_events_are_buffered_until_the_batch_fills(store: Store, a_stage: Stage) -> None:
    run_id = start(store)
    run_stage_id = store.register_stage(run_id, 0, a_stage)
    record_id = store.add_record(run_id, 0, {"id": "1"})

    for _ in range(BATCH_SIZE - 1):
        store.add_record_event(
            record_id=record_id,
            run_stage_id=run_stage_id,
            status="ok",
            record_input={"id": "1"},
            record_output={"id": "1"},
            duration_us=1,
        )
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM record_events").fetchone()[0] == 0

    store.add_record_event(
        record_id=record_id,
        run_stage_id=run_stage_id,
        status="ok",
        record_input={"id": "1"},
        record_output={"id": "1"},
        duration_us=1,
    )
    with sqlite3.connect(store.path) as connection:
        written = connection.execute("SELECT COUNT(*) FROM record_events").fetchone()[0]
    assert written == BATCH_SIZE


def test_an_unserializable_value_is_still_recorded() -> None:
    stored = json.loads(to_json({"id": "1", "when": object()}))

    assert stored["id"] == "1"
    assert stored["when"]["__squeegee_unserializable__"].startswith("<object object")


def test_a_second_record_at_the_same_index_is_rejected(store: Store) -> None:
    run_id = start(store)
    store.add_record(run_id, 0, {"id": "1"})

    with pytest.raises(sqlite3.IntegrityError):
        store.add_record(run_id, 0, {"id": "2"})


def test_the_database_is_created_with_its_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "deeply" / "nested" / "squeegee.db"

    with Store(path):
        pass

    assert path.exists()
