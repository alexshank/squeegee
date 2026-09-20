"""Tests for the read side, against a database built by the real example pipeline."""

import sqlite3
import statistics
from pathlib import Path

import pytest

from squeegee.cli import main
from squeegee.errors import SqueegeeError
from squeegee.stages import clear_registry
from squeegee.store import queries
from squeegee.store.sqlite import Store

EXAMPLES = Path(__file__).parents[2] / "examples"


@pytest.fixture(scope="module")
def database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Three runs of one script: clean, failed, and continued past the failure."""
    path = tmp_path_factory.mktemp("example") / "squeegee.db"
    script = str(EXAMPLES / "clean_orders.py")
    for arguments in (
        ["--input", str(EXAMPLES / "orders.csv")],
        ["--input", str(EXAMPLES / "orders_with_a_bad_row.csv")],
        ["--input", str(EXAMPLES / "orders_with_a_bad_row.csv"), "--continue-on-error"],
    ):
        clear_registry()
        main(["run", script, "--db", str(path), "--quiet", *arguments])
    clear_registry()
    return path


def run_once(script: Path, source: Path, database: Path) -> None:
    clear_registry()
    main(["run", str(script), "--input", str(source), "--db", str(database), "--quiet"])
    clear_registry()


def test_meta_counts_the_runs(database: Path) -> None:
    assert queries.meta(database)["run_count"] == 3


def test_runs_are_listed_newest_first_with_counts(database: Path) -> None:
    listed = queries.list_runs(database)

    assert [run["run_id"] for run in listed["items"]] == [3, 2, 1]
    assert listed["has_more"] is False
    assert listed["items"][2]["records_in"] == 10
    assert listed["items"][2]["records_out"] == 6
    assert listed["items"][1]["status"] == "failed"
    assert listed["items"][0]["duration_us"] > 0


def test_pagination_returns_every_run_exactly_once(database: Path) -> None:
    seen: list[int] = []
    cursor: str | None = None
    while True:
        page = queries.list_runs(database, limit=2, cursor=cursor)
        seen.extend(run["run_id"] for run in page["items"])
        if not page["has_more"]:
            break
        cursor = page["next_cursor"]

    assert seen == [3, 2, 1]


def test_runs_can_be_filtered_by_script(database: Path) -> None:
    assert queries.list_runs(database, script="clean_orders")["items"] != []
    assert queries.list_runs(database, script="nothing_like_this")["items"] == []


def test_a_failed_run_reports_the_stage_and_record_that_stopped_it(database: Path) -> None:
    summary = queries.run_summary(database, 2)

    assert summary["status"] == "failed"
    assert summary["failure"] == {
        "stage_position": 2,
        "stage_name": "parse_amount",
        "record_index": 8,
        "error_type": "ValueError",
        "error_message": "could not convert string to float: 'n/a'",
    }
    assert summary["options"]["continue_on_error"] is False
    assert [stage["name"] for stage in summary["stages"]][:2] == [
        "normalize_headers",
        "drop_internal_test_orders",
    ]
    assert summary["stages"][1]["records_dropped"] == 2


def test_a_finished_run_has_no_failure(database: Path) -> None:
    assert queries.run_summary(database, 1)["failure"] is None


def test_an_unknown_run_is_an_error(database: Path) -> None:
    with pytest.raises(SqueegeeError, match="no run 99"):
        queries.run_summary(database, 99)


def test_stage_detail_carries_the_source_that_ran(database: Path) -> None:
    detail = queries.stage_detail(database, 2, 2)

    assert detail["name"] == "parse_amount"
    assert "def parse_amount" in detail["source_text"]
    assert detail["source_language"] == "python"
    assert (detail["input_type"], detail["output_type"]) == (None, None)
    # the same unedited stage was used by the other two runs
    assert detail["also_used_by_runs"] == [1, 3]
    assert detail["counts"]["records_errored"] == 1


def test_stage_detail_of_an_unknown_position_is_an_error(database: Path) -> None:
    with pytest.raises(SqueegeeError, match="no stage at position 9"):
        queries.stage_detail(database, 1, 9)


def test_stage_records_can_be_filtered_by_status(database: Path) -> None:
    errors = queries.stage_records(database, 2, 2, status="error")

    assert [event["record_index"] for event in errors["items"]] == [8]
    assert errors["items"][0]["output"] is None
    assert errors["items"][0]["error_type"] == "ValueError"


def test_stage_records_can_be_searched(database: Path) -> None:
    found = queries.stage_records(database, 1, 2, search="grace@example.com")

    assert [event["record_index"] for event in found["items"]] == [2, 5]


def test_stage_records_paginate(database: Path) -> None:
    seen: list[int] = []
    cursor: str | None = None
    while True:
        page = queries.stage_records(database, 1, 0, limit=3, cursor=cursor)
        seen.extend(event["record_index"] for event in page["items"])
        if not page["has_more"]:
            break
        cursor = page["next_cursor"]

    assert seen == list(range(10))


def test_an_unknown_status_is_rejected(database: Path) -> None:
    with pytest.raises(SqueegeeError, match="status must be ok, dropped, or error"):
        queries.stage_records(database, 1, 0, status="broken")


def test_a_trace_ends_where_the_record_failed(database: Path) -> None:
    trace = queries.record_trace(database, 2, 8)

    assert trace["final_status"] == "error"
    assert [event["position"] for event in trace["events"]] == [0, 1, 2]
    assert trace["events"][2]["error_message"].endswith("'n/a'")
    assert trace["source"]["Order ID"] == "1008"


def test_a_trace_marks_the_fields_a_stage_changed(database: Path) -> None:
    trace = queries.record_trace(database, 1, 0)

    assert trace["events"][0]["changed_fields"] == [
        "Amount",
        "Email",
        "Order ID",
        "Placed On",
        "amount",
        "email",
        "order_id",
        "placed_on",
    ]
    assert trace["events"][2]["changed_fields"] == ["amount", "amount_cents"]
    assert trace["final_status"] == "ok"


def test_a_trace_steps_to_the_neighbouring_record(database: Path) -> None:
    trace = queries.record_trace(database, 1, 3)

    assert (trace["previous_record_index"], trace["next_record_index"]) == (2, 4)


def test_stepping_can_be_restricted_to_one_status(database: Path) -> None:
    # records 1 and 6 are the internal test accounts, dropped at stage 1
    trace = queries.record_trace(database, 1, 3, status="dropped")

    assert (trace["previous_record_index"], trace["next_record_index"]) == (1, 5)


def test_an_unknown_record_is_an_error(database: Path) -> None:
    with pytest.raises(SqueegeeError, match="no record 999"):
        queries.record_trace(database, 1, 999)


def test_field_statistics_match_the_values_themselves(database: Path) -> None:
    fields = queries.stage_fields(database, 1, 2)
    amounts = [
        event["output"]["amount_cents"]
        for event in queries.stage_records(database, 1, 2, status="ok")["items"]
    ]
    cents = next(field for field in fields["items"] if field["field"] == "amount_cents")

    assert fields["records_considered"] == len(amounts)
    assert cents["inferred_type"] == "number"
    assert cents["non_null_count"] == len(amounts)
    assert cents["null_count"] == 0
    assert cents["sum"] == sum(amounts)
    assert cents["mean"] == pytest.approx(statistics.mean(amounts))
    assert cents["median"] == pytest.approx(statistics.median_low(amounts))
    assert (cents["min"], cents["max"]) == (min(amounts), max(amounts))


def test_a_text_field_has_no_numeric_statistics(database: Path) -> None:
    fields = queries.stage_fields(database, 1, 2)
    email = next(field for field in fields["items"] if field["field"] == "email")

    assert email["inferred_type"] == "string"
    assert (email["min"], email["mean"], email["sum"]) == (None, None, None)
    assert email["distinct_count"] == 7


def test_a_numeric_field_gets_a_histogram_and_its_before(database: Path) -> None:
    detail = queries.field_detail(database, 1, 2, "amount_cents", bins=5)

    assert detail["inferred_type"] == "number"
    assert len(detail["after"]["histogram"]) == 5
    assert sum(bucket["count"] for bucket in detail["after"]["histogram"]) == 8
    assert detail["after"]["top_values"] is None
    # before this stage the column was the currency string it was parsed from
    assert detail["before"] is None


def test_a_text_field_gets_top_values_before_and_after(database: Path) -> None:
    detail = queries.field_detail(database, 1, 4, "email", top=3)

    assert detail["after"]["histogram"] is None
    assert detail["after"]["top_values"][0]["count"] == 1
    assert detail["before"] is not None
    assert {value["value"] for value in detail["before"]["top_values"]} <= {
        "ada@example.com",
        "grace@example.com",
        "linus@example.com",
        "margaret@example.com",
        "katherine@example.com",
        "barbara@example.com",
    }


def test_field_detail_rejects_bins_and_top_outside_their_range(database: Path) -> None:
    with pytest.raises(SqueegeeError, match="bins must be between 5 and 50"):
        queries.field_detail(database, 1, 2, "amount_cents", bins=2)
    with pytest.raises(SqueegeeError, match="top must be between 1 and 100"):
        queries.field_detail(database, 1, 2, "email", top=0)


def test_an_unknown_field_is_an_error(database: Path) -> None:
    with pytest.raises(SqueegeeError, match="has no field 'nope'"):
        queries.field_detail(database, 1, 2, "nope")


def test_a_missing_database_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(SqueegeeError, match="no squeegee database"):
        queries.meta(tmp_path / "absent.db")


def test_queries_never_hold_a_writable_connection(database: Path) -> None:
    connection = queries._read_only(database)

    with pytest.raises(sqlite3.OperationalError, match=r"readonly|read-only"):
        connection.execute("INSERT INTO runs (started_at) VALUES ('now')")


MIXED_SCRIPT = '''
from squeegee import stage


@stage
def mix_the_types(record):
    """Emit a number for some records and a string for others."""
    record["v"] = int(record["id"]) if int(record["id"]) % 2 else record["id"]
    return record


@stage
def never_reached(record):
    """Only runs when the first stage did not stop the run."""
    return record
'''


def test_a_field_holding_two_types_is_reported_as_mixed(tmp_path: Path) -> None:
    script, database = tmp_path / "mixed.py", tmp_path / "squeegee.db"
    script.write_text(MIXED_SCRIPT)
    (tmp_path / "in.csv").write_text("id\n1\n2\n3\n")
    run_once(script, tmp_path / "in.csv", database)

    fields = queries.stage_fields(database, 1, 0)

    assert next(field for field in fields["items"] if field["field"] == "v")["inferred_type"] == (
        "mixed"
    )


FAILING_SCRIPT = '''
from squeegee import stage


@stage
def fail_immediately(record):
    """Stop the run on the very first record."""
    raise RuntimeError("stopped at once")


@stage
def never_runs(record):
    """No record ever reaches this stage."""
    return record
'''


def test_a_stage_that_never_ran_reports_no_durations(tmp_path: Path) -> None:
    script, database = tmp_path / "failing.py", tmp_path / "squeegee.db"
    script.write_text(FAILING_SCRIPT)
    (tmp_path / "in.csv").write_text("id\n1\n")
    run_once(script, tmp_path / "in.csv", database)

    untouched = queries.run_summary(database, 1)["stages"][1]

    assert untouched["records_in"] == 0
    assert untouched["duration_us_median"] is None
    assert untouched["duration_us_p95"] is None


def test_a_run_still_in_progress_has_no_duration(tmp_path: Path) -> None:
    database = tmp_path / "squeegee.db"
    store = Store(database)
    store.start_run(
        script_path=Path("script.py"),
        script_sha256="abc",
        input_path=Path("in.csv"),
        output_path=None,
        options={},
    )
    store.close()

    listed = queries.list_runs(database)["items"][0]

    assert (listed["status"], listed["ended_at"], listed["duration_us"]) == ("started", None, None)
