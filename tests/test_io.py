"""Tests for the reader and writer layer."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from squeegee.errors import FormatError
from squeegee.io import (
    clear_readers,
    read_records,
    reader_for,
    register_reader,
    write_records,
)
from squeegee.io.text_io import blocks_starting_with

Record = dict[str, Any]

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


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('{"id": "1"}\n{"id": "2"}\n', [{"id": "1"}, {"id": "2"}]),
        ("id,amount\n1,$29.99\n2,$4.00\n", RECORDS),
        ("just some notes", [{"line_number": 1, "text": "just some notes"}]),
    ],
    ids=["json", "csv", "plain text"],
)
def test_an_unknown_extension_is_read_by_its_content(
    tmp_path: Path, content: str, expected: list[Record]
) -> None:
    path = tmp_path / "export.dat"
    path.write_text(content)

    assert list(read_records(path)) == expected


def test_each_record_carries_the_raw_slice_it_was_read_from(tmp_path: Path) -> None:
    path = tmp_path / "quoted.csv"
    path.write_text('id,note\n1,"two\nlines"\n2,plain\n')

    assert [raw for raw, _ in reader_for(path)(path)] == [
        'id,note\n1,"two\nlines"',
        "id,note\n2,plain",
    ]


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


def test_a_text_file_reads_as_one_record_per_block(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("first note\n\n\nsecond note\nstill the second\n")

    assert list(read_records(path)) == [
        {"line_number": 1, "text": "first note"},
        {"line_number": 4, "text": "second note\nstill the second"},
    ]


def test_a_block_reader_keeps_the_blank_lines_inside_an_entry(tmp_path: Path) -> None:
    path = tmp_path / "journal.txt"
    path.write_text("a title\n\n01/01 - one\n\n  continued\n\n01/02 - two\n")

    records = [record for _, record in blocks_starting_with(r"\d{1,2}/\d{1,2}")(path)]

    assert records == [
        {"line_number": 1, "text": "a title"},
        {"line_number": 3, "text": "01/01 - one\n\n  continued"},
        {"line_number": 7, "text": "01/02 - two"},
    ]


def test_a_registered_reader_wins_until_the_readers_are_cleared(tmp_path: Path) -> None:
    path = tmp_path / "journal.txt"
    path.write_text("01/01 - one\n\ncontinued\n")
    register_reader(".TXT", blocks_starting_with(r"\d{1,2}/\d{1,2}"))

    assert len(list(read_records(path))) == 1

    clear_readers()

    assert len(list(read_records(path))) == 2


def test_csv_text_records_are_written_as_their_rows(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"

    assert write_records(path, ["id,amount\n1,$29.99", "id,amount\n2,$4.00"]) == 2  # type: ignore[list-item]
    assert list(read_records(path)) == RECORDS
