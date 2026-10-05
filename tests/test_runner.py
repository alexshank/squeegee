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
    assert (1, 1, "dropped") in events(workspace)
    assert not [event for event in events(workspace) if event[0] == 1 and event[1] == 2]


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
    # the two records processed before the failure are still recorded, after
    # stage zero read all three
    assert len([event for event in events(workspace) if event[2] == "ok"]) == 8
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
        "JOIN run_stages ON run_stages.id = run_stage_id WHERE record_index = 0 AND position = 1",
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
        "JOIN records ON records.id = record_id "
        "JOIN run_stages ON run_stages.id = run_stage_id WHERE record_index = 0 AND position = 1",
    )[0]
    assert json.loads(source) == json.loads(first_input)


def test_stage_zero_records_the_raw_row_each_record_was_read_from(workspace: Path) -> None:
    @stage
    def identity(record: Record) -> Record:
        return record

    execute(workspace)

    name, kind, raw, read = events(
        workspace,
        "SELECT sv.name, sv.kind, e.input_json, e.output_json FROM record_events e "
        "JOIN records r ON r.id = e.record_id JOIN run_stages rs ON rs.id = e.run_stage_id "
        "JOIN stage_versions sv ON sv.id = rs.stage_version_id "
        "WHERE r.record_index = 0 AND rs.position = 0",
    )[0]
    assert (name, kind) == ("read_csv", "source")
    assert json.loads(raw) == "id,amount\n1,$29.99"
    assert json.loads(read) == {"id": "1", "amount": "$29.99"}


def test_the_writer_is_the_last_stage_and_records_each_written_row(workspace: Path) -> None:
    @stage
    def identity(record: Record) -> Record:
        return record

    execute(workspace)

    name, kind, record, written = events(
        workspace,
        "SELECT sv.name, sv.kind, e.input_json, e.output_json FROM record_events e "
        "JOIN records r ON r.id = e.record_id JOIN run_stages rs ON rs.id = e.run_stage_id "
        "JOIN stage_versions sv ON sv.id = rs.stage_version_id "
        "WHERE r.record_index = 0 AND rs.position = 2",
    )[0]
    assert (name, kind) == ("write_csv", "accumulator")
    assert json.loads(record) == {"id": "1", "amount": "$29.99"}
    # the slice is what the file holds, CSV's own line ending included
    assert json.loads(written) == "id,amount\r\n1,$29.99"


def test_the_script_input_and_output_files_are_kept(workspace: Path) -> None:
    @stage
    def identity(record: Record) -> Record:
        return record

    execute(workspace)

    kept = dict(events(workspace, "SELECT role, content FROM run_files"))
    # bytes, so the CSV writer's \r\n line endings are kept as written
    assert kept["script"] == (workspace / "clean.py").read_bytes()
    assert kept["input"] == (workspace / "orders.csv").read_bytes()
    assert kept["output"] == (workspace / "clean.csv").read_bytes()
    assert b"\r\n" in kept["output"]


def test_a_writer_failing_partway_fails_the_run_and_writes_nothing(workspace: Path) -> None:
    @stage
    def widen_the_second(record: Record) -> Record:
        return {**record, "extra": "x"} if record["id"] == "2" else record

    (workspace / "clean.csv").write_text("an earlier output\n")

    result = execute(workspace)

    assert result.status == "failed"
    assert result.failure is not None
    assert (result.failure.stage_name, result.failure.record_index) == ("write_csv", 1)
    # the earlier output is untouched and no partial file is left beside it
    assert (workspace / "clean.csv").read_text() == "an earlier output\n"
    assert [path.name for path in workspace.iterdir() if "partial" in path.name] == []
    assert (1, 2, "error") in events(workspace)
    assert events(workspace, "SELECT role FROM run_files WHERE role = 'output'") == []


def test_a_record_of_csv_text_with_two_rows_is_one_written_slice(workspace: Path) -> None:
    @stage
    def two_rows(record: Record) -> str:
        return f"id\n{record['id']}a\n{record['id']}b"

    execute(workspace)

    written = events(
        workspace,
        "SELECT e.output_json FROM record_events e JOIN run_stages rs ON rs.id = e.run_stage_id "
        "WHERE rs.position = 2",
    )
    assert len(written) == 3
    assert json.loads(written[0][0]) == "id\r\n1a\r\n1b"
    assert (workspace / "clean.csv").read_text().count("\n") == 7


def test_without_an_output_there_is_no_accumulator(workspace: Path) -> None:
    @stage
    def identity(record: Record) -> Record:
        return record

    execute(workspace, output=False)

    assert events(workspace, "SELECT COUNT(*) FROM run_stages")[0][0] == 2
    assert events(workspace, "SELECT role FROM run_files WHERE role = 'output'") == []


def test_limit_processes_only_the_first_records(workspace: Path) -> None:
    @stage
    def identity(record: Record) -> Record:
        return record

    assert execute(workspace, limit=2).records_in == 2


@pytest.mark.parametrize("option", ["limit", "sample"])
def test_a_negative_count_is_refused_before_the_run_starts(workspace: Path, option: str) -> None:
    @stage
    def identity(record: Record) -> Record:
        return record

    with pytest.raises(SqueegeeError, match="must be 0 or more"):
        execute(workspace, **{option: -1})  # type: ignore[arg-type]
    assert not (workspace / ".squeegee" / "squeegee.db").exists()


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
