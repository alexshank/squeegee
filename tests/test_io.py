"""Tests for the reader and writer layer."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from squeegee.errors import FormatError
from squeegee.io import read_records, write_records

RECORDS = [
    {"id": "1", "amount": "$29.99"},
    {"id": "2", "amount": "$4.00"},
]


@pytest.mark.parametrize("suffix", [".csv", ".json", ".jsonl", ".ndjson"])
def test_records_survive_a_round_trip(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"records{suffix}"

    assert write_records(path, RECORDS) == 2
    assert list(read_records(path)) == RECORDS


def test_a_json_array_and_json_lines_read_the_same(tmp_path: Path) -> None:
    array = tmp_path / "array.json"
    array.write_text(json.dumps(RECORDS))
    lines = tmp_path / "lines.jsonl"
    lines.write_text("\n".join(json.dumps(record) for record in RECORDS) + "\n")

    assert list(read_records(array)) == list(read_records(lines))


def test_leading_whitespace_does_not_hide_an_array(tmp_path: Path) -> None:
    path = tmp_path / "padded.json"
    path.write_text("\n\n   " + json.dumps(RECORDS))

    assert list(read_records(path)) == RECORDS


def test_blank_lines_between_records_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "gappy.jsonl"
    path.write_text(json.dumps(RECORDS[0]) + "\n\n" + json.dumps(RECORDS[1]) + "\n")

    assert list(read_records(path)) == RECORDS


def test_reading_is_lazy(tmp_path: Path) -> None:
    # the second line is unparseable, so reading the first record can only work
    # if records are not materialized up front
    path = tmp_path / "broken_later.jsonl"
    path.write_text(json.dumps(RECORDS[0]) + "\nnot json at all\n")

    records = read_records(path)
    assert isinstance(records, Iterator)
    assert next(records) == RECORDS[0]
    with pytest.raises(FormatError, match="line 2 is not valid JSON"):
        next(records)


def test_an_unknown_extension_fails_before_the_file_is_opened(tmp_path: Path) -> None:
    missing = tmp_path / "orders.parquet"

    with pytest.raises(FormatError, match="not supported") as raised:
        list(read_records(missing))

    assert "orders.parquet" in str(raised.value)
    assert ".csv" in str(raised.value)


def test_a_file_with_no_extension_says_so(tmp_path: Path) -> None:
    with pytest.raises(FormatError, match="no extension"):
        list(read_records(tmp_path / "orders"))


def test_writing_an_unknown_extension_fails(tmp_path: Path) -> None:
    with pytest.raises(FormatError, match="not supported"):
        write_records(tmp_path / "out.parquet", RECORDS)


def test_a_lone_json_object_is_read_as_one_record(tmp_path: Path) -> None:
    path = tmp_path / "object.json"
    path.write_text('  {"id": "1"}')

    assert list(read_records(path)) == [{"id": "1"}]


def test_an_array_of_scalars_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "scalars.json"
    path.write_text("[1, 2]")

    with pytest.raises(FormatError, match="element 0 holds int, not an object"):
        list(read_records(path))


def test_json_lines_holding_a_scalar_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "scalar.jsonl"
    path.write_text("42\n")

    with pytest.raises(FormatError, match="not an object"):
        list(read_records(path))


def test_a_csv_record_with_different_fields_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "ragged.csv"

    with pytest.raises(FormatError, match="every record must have the same fields"):
        write_records(path, [{"id": "1"}, {"id": "2", "extra": "x"}])


def test_an_empty_input_writes_an_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"

    assert write_records(path, []) == 0
    assert list(read_records(path)) == []


def test_an_empty_json_file_reads_as_no_records(tmp_path: Path) -> None:
    path = tmp_path / "blank.json"
    path.write_text("   \n\n")

    assert list(read_records(path)) == []
