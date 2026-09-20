"""Tests for the execution engine."""

import csv
import json
import sqlite3
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from squeegee.errors import FormatError, SqueegeeError
from squeegee.runner import RunResult, run
from squeegee.stages import clear_registry, stage

Record = dict[str, Any]


@pytest.fixture(autouse=True)
def _empty_registry() -> Iterator[None]:
    clear_registry()
    yield
    clear_registry()


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "clean.py").write_text("# the script squeegee hashes for provenance\n")
    _write_csv(
        tmp_path / "orders.csv",
        [
            {"id": "1", "amount": "$29.99"},
            {"id": "2", "amount": "$4.00"},
            {"id": "3", "amount": "$130.00"},
        ],
    )
    return tmp_path


def _write_csv(path: Path, records: list[Record]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def execute(workspace: Path, *, output: bool = True, **options: Any) -> RunResult:
    return run(
        script_path=workspace / "clean.py",
        input_path=workspace / "orders.csv",
        output_path=workspace / "clean.csv" if output else None,
        database_path=workspace / ".squeegee" / "squeegee.db",
        **options,
    )


def events(workspace: Path, sql: str = "") -> list[tuple[Any, ...]]:
    with sqlite3.connect(workspace / ".squeegee" / "squeegee.db") as connection:
        return connection.execute(
            sql
            or "SELECT r.record_index, rs.position, e.status FROM record_events e "
            "JOIN records r ON r.id = e.record_id "
            "JOIN run_stages rs ON rs.id = e.run_stage_id "
            "ORDER BY r.record_index, rs.position"
        ).fetchall()


def test_records_flow_through_stages_in_declaration_order(workspace: Path) -> None:
    @stage
    def to_cents(record: Record) -> Record:
        record["amount_cents"] = round(float(record.pop("amount").lstrip("$")) * 100)
        return record

    @stage
    def tag(record: Record) -> Record:
        record["seen"] = "yes"
        return record

    result = execute(workspace)

    assert (result.status, result.records_in, result.records_out) == ("finished", 3, 3)
    written = list(csv.DictReader((workspace / "clean.csv").open()))
    assert written[0] == {"id": "1", "amount_cents": "2999", "seen": "yes"}


def test_returning_none_drops_the_record_and_later_stages_never_see_it(workspace: Path) -> None:
    seen_by_second: list[str] = []

    @stage
    def drop_the_second(record: Record) -> Record | None:
        return None if record["id"] == "2" else record

    @stage
    def watch(record: Record) -> Record:
        seen_by_second.append(record["id"])
        return record

    result = execute(workspace)

    assert (result.records_dropped, result.records_out) == (1, 2)
    assert seen_by_second == ["1", "3"]
    assert (1, 0, "dropped") in events(workspace)
    assert not [event for event in events(workspace) if event[0] == 1 and event[1] == 1]


def test_a_raising_stage_aborts_the_run_and_keeps_what_came_before(workspace: Path) -> None:
    @stage
    def parse_amount(record: Record) -> Record:
        record["amount_cents"] = round(float(record["amount"].lstrip("$")) * 100)
        return record

    @stage
    def reject_the_third(record: Record) -> Record:
        if record["id"] == "3":
            raise ValueError("could not convert string to float: 'n/a'")
        return record

    result = execute(workspace)

    assert result.status == "failed"
    assert result.failure is not None
    assert (result.failure.stage_name, result.failure.record_index) == ("reject_the_third", 2)
    assert result.failure.error_type == "ValueError"
    assert result.records_in == 3
    # the two records processed before the failure are still recorded
    assert len([event for event in events(workspace) if event[2] == "ok"]) == 5
    assert not (workspace / "clean.csv").exists()


def test_continue_on_error_records_the_failure_and_finishes(workspace: Path) -> None:
    @stage
    def reject_the_second(record: Record) -> Record:
        if record["id"] == "2":
            raise ValueError("bad row")
        return record

    result = execute(workspace, continue_on_error=True)

    assert (result.status, result.records_errored, result.records_out) == ("finished", 1, 2)
    assert (workspace / "clean.csv").exists()


def test_the_error_is_stored_with_its_traceback(workspace: Path) -> None:
    @stage
    def always_raises(record: Record) -> Record:
        raise KeyError("missing_column")

    execute(workspace)

    stored = events(
        workspace,
        "SELECT error_type, error_message, error_traceback FROM record_events "
        "WHERE status = 'error'",
    )[0]
    assert stored[0] == "KeyError"
    assert "missing_column" in stored[1]
    assert "Traceback" in stored[2]


def test_a_stage_mutating_in_place_does_not_corrupt_the_stored_input(workspace: Path) -> None:
    @stage
    def mutate(record: Record) -> Record:
        record["amount"] = "rewritten"
        return record

    execute(workspace)

    stored = events(
        workspace,
        "SELECT input_json FROM record_events JOIN records ON records.id = record_id "
        "WHERE record_index = 0",
    )[0][0]
    assert json.loads(stored)["amount"] == "$29.99"


def test_the_first_stage_sees_the_record_as_read(workspace: Path) -> None:
    @stage
    def identity(record: Record) -> Record:
        return record

    execute(workspace)

    source, first_input = events(
        workspace,
        "SELECT records.source_json, record_events.input_json FROM record_events "
        "JOIN records ON records.id = record_id WHERE record_index = 0",
    )[0]
    assert json.loads(source) == json.loads(first_input)


def test_limit_processes_only_the_first_records(workspace: Path) -> None:
    @stage
    def identity(record: Record) -> Record:
        return record

    assert execute(workspace, limit=2).records_in == 2


def test_sampling_is_reproducible_with_a_seed(workspace: Path) -> None:
    @stage
    def identity(record: Record) -> Record:
        return record

    first = execute(workspace, sample=2, seed=7)
    second = execute(workspace, sample=2, seed=7)

    assert first.records_in == second.records_in == 2
    sampled = events(
        workspace,
        "SELECT run_id, source_json FROM records ORDER BY run_id, record_index",
    )
    assert [row[1] for row in sampled[:2]] == [row[1] for row in sampled[2:]]


def test_a_run_without_an_output_path_still_records_everything(workspace: Path) -> None:
    @stage
    def identity(record: Record) -> Record:
        return record

    result = execute(workspace, output=False)

    assert result.records_out == 3
    assert not (workspace / "clean.csv").exists()


def test_a_script_with_no_stages_fails_before_reading_anything(workspace: Path) -> None:
    with pytest.raises(SqueegeeError, match="registered no stages"):
        execute(workspace)


def test_a_missing_input_fails_before_the_run_starts(workspace: Path) -> None:
    @stage
    def identity(record: Record) -> Record:
        return record

    with pytest.raises(SqueegeeError, match="does not exist"):
        run(
            script_path=workspace / "clean.py",
            input_path=workspace / "absent.csv",
            output_path=None,
            database_path=workspace / ".squeegee" / "squeegee.db",
        )

    assert not (workspace / ".squeegee").exists()


def test_an_unsupported_output_extension_fails_before_the_run_starts(workspace: Path) -> None:
    @stage
    def identity(record: Record) -> Record:
        return record

    with pytest.raises(FormatError, match="not supported"):
        run(
            script_path=workspace / "clean.py",
            input_path=workspace / "orders.csv",
            output_path=workspace / "clean.parquet",
            database_path=workspace / ".squeegee" / "squeegee.db",
        )


@pytest.mark.slow
def test_ten_thousand_records_through_five_stages_stay_under_five_seconds(
    workspace: Path,
) -> None:
    _write_csv(
        workspace / "orders.csv",
        [{"id": str(number), "amount": f"${number}.00"} for number in range(10_000)],
    )
    for _ in range(5):

        @stage
        def touch(record: Record) -> Record:
            record["touched"] = record["id"]
            return record

    started = time.perf_counter()
    result = execute(workspace)
    elapsed = time.perf_counter() - started

    assert result.records_out == 10_000
    assert elapsed < 5.0, f"took {elapsed:.2f}s"
