"""Readers and writers.

A reader yields ``(raw, record)`` pairs: the slice of the input a record came
from, and the record parsed out of it. The runner records each pair as the
source stage's input and output, so how the input was broken up is visible in
the run like any other stage.

A reader is resolved by extension, then by sniffing the content, falling back
to plain text. Adding a format means adding a module here and an entry to the
tables below. A file whose shape only its own script knows is handled instead
by calling ``register_reader``.
"""

import csv
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any, TypeVar

from squeegee.errors import FormatError
from squeegee.io import csv_io, json_io, text_io

Record = dict[str, Any]
Reader = Callable[[Path], Iterator[tuple[str, Record]]]
Resolved = TypeVar("Resolved")

_READERS: dict[str, Reader] = {
    ".csv": csv_io.read_csv,
    ".json": json_io.read_json,
    ".jsonl": json_io.read_json,
    ".ndjson": json_io.read_json,
    ".txt": text_io.read_text,
    ".md": text_io.read_text,
}

# what the UI highlights a reader's raw slices as; anything else it infers
FORMATS: dict[Reader, str] = {csv_io.read_csv: "csv", json_io.read_json: "json"}

# a reader a script registered for itself, which wins over the table above
_CUSTOM_READERS: dict[str, Reader] = {}

_WRITERS = {
    ".csv": csv_io.write,
    ".json": json_io.write_array,
    ".jsonl": json_io.write_lines,
    ".ndjson": json_io.write_lines,
}


def read_records(path: Path) -> Iterator[Record]:
    """Yield the records of ``path`` one at a time, without their raw slices."""
    return (record for _, record in reader_for(path)(path))


def write_records(path: Path, records: Iterable[Record]) -> int:
    """Write ``records`` to ``path`` and return how many were written.

    Raises:
        FormatError: The extension is unsupported.
    """
    return writer_for(path)(path, records)


def reader_for(path: Path) -> Reader:
    """Return the reader for ``path``: by extension, then by content, then plain text."""
    readers = {**_READERS, **_CUSTOM_READERS}
    return readers.get(path.suffix.lower()) or _sniff(path)


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


def writer_for(path: Path) -> Callable[[Path, Iterable[Record]], int]:
    """Return the writer for ``path``, so a run can fail before it starts."""
    return _resolve(_WRITERS, path)


def _resolve(table: dict[str, Resolved], path: Path) -> Resolved:
    try:
        return table[path.suffix.lower()]
    except KeyError:
        supported = ", ".join(sorted(table))
        raise FormatError(
            f"cannot handle {path.name!r}: {path.suffix or 'no extension'} is not supported. "
            f"Supported extensions: {supported}"
        ) from None


def _sniff(path: Path) -> Reader:
    with path.open(encoding="utf-8", errors="replace") as handle:
        sample = handle.read(64 * 1024)
    if sample.lstrip()[:1] in ("[", "{"):
        return json_io.read_json
    try:
        # the CSV reader is comma only, so sniffing for any other delimiter would lie
        csv.Sniffer().sniff(sample, delimiters=",")
        if csv.Sniffer().has_header(sample):
            return csv_io.read_csv
    except csv.Error:
        pass
    return text_io.read_text
