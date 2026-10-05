"""Readers and writers.

A reader yields ``(raw, record)`` pairs: the slice of the input a record came
from, and the record parsed out of it. The runner records each pair as the
source stage's input and output, so how the input was broken up is visible in
the run like any other stage. A writer mirrors it: it yields the slice each
record was written as, recorded as the accumulator stage's output.

A reader is resolved by extension, then by sniffing the content, falling back
to plain text. Adding a format means adding a module here and an entry to the
tables below. A file whose shape only its own script knows is handled instead
by calling ``register_reader``.
"""

import csv
import json
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any

from squeegee.errors import FormatError
from squeegee.io import csv_io, json_io, text_io

Record = dict[str, Any]
Reader = Callable[[Path], Iterator[tuple[str, Record]]]
# a writer yields each record's written slice, so the run can record it like a read one
Writer = Callable[[Path, Iterable[Record]], Iterator[str]]

_READERS: dict[str, Reader] = {
    ".csv": csv_io.read_csv,
    ".json": json_io.read_json,
    ".jsonl": json_io.read_json,
    ".ndjson": json_io.read_json,
    ".txt": text_io.read_text,
    ".md": text_io.read_text,
}

# what the UI highlights a file and its raw slices as; anything else it infers
FORMATS: dict[Reader | Writer, str] = {
    csv_io.read_csv: "csv",
    csv_io.write_csv: "csv",
    json_io.read_json: "json",
    json_io.write_json: "json",
    json_io.write_json_lines: "json",
}

# a reader a script registered for itself, which wins over the table above
_CUSTOM_READERS: dict[str, Reader] = {}

_WRITERS: dict[str, Writer] = {
    ".csv": csv_io.write_csv,
    ".json": json_io.write_json,
    ".jsonl": json_io.write_json_lines,
    ".ndjson": json_io.write_json_lines,
}


def read_records(path: Path) -> Iterator[Record]:
    """Yield the records of ``path`` one at a time, without their raw slices."""
    return (record for _, record in reader_for(path)(path))


def write_records(path: Path, records: Iterable[Record]) -> int:
    """Write ``records`` to ``path`` and return how many were written.

    Raises:
        FormatError: The extension is unsupported.
    """
    return len(list(writer_for(path)(path, records)))


def reader_for(path: Path) -> Reader:
    """Return the reader for ``path``: by extension, then by content, then plain text."""
    suffix = path.suffix.lower()
    return _CUSTOM_READERS.get(suffix) or _READERS.get(suffix) or _sniff(path)


def register_reader(suffix: str, reader: Reader) -> None:
    """Read ``suffix`` with ``reader`` for the rest of this run.

    A script calls this when its input has a shape no extension can imply, such
    as a text file whose entries are delimited by something only that file uses.
    The reader yields ``(raw, record)`` pairs, like the built-in ones.
    """
    _CUSTOM_READERS[suffix.lower()] = reader


def clear_readers() -> None:
    """Forget every registered reader.

    Two scripts run in one process, which the tests do constantly, would
    otherwise inherit each other's readers.
    """
    _CUSTOM_READERS.clear()


def writer_for(path: Path) -> Writer:
    """Return the writer for ``path``, so a run can fail before it starts."""
    try:
        return _WRITERS[path.suffix.lower()]
    except KeyError:
        raise FormatError(
            f"cannot handle {path.name!r}: {path.suffix or 'no extension'} is not supported. "
            f"Supported extensions: {', '.join(sorted(_WRITERS))}"
        ) from None


def _sniff(path: Path) -> Reader:
    # squeegee is for small data, so reading the whole file to decide is affordable
    text = path.read_text(encoding="utf-8", errors="replace")
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    # a leading bracket is not enough: a log of "[INFO] ..." lines is not JSON
    if _holds_json(first_line) or _holds_json(text):
        return json_io.read_json
    sample = text[: 64 * 1024]
    try:
        # the CSV reader is comma only, so sniffing for any other delimiter would lie
        csv.Sniffer().sniff(sample, delimiters=",")
        if csv.Sniffer().has_header(sample):
            return csv_io.read_csv
    except csv.Error:
        pass
    return text_io.read_text


def _holds_json(text: str) -> bool:
    try:
        return isinstance(json.loads(text), dict | list)
    except json.JSONDecodeError:
        return False
