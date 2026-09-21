"""Readers and writers, resolved by file extension.

CSV, JSON and plain text cover what lands on a developer's desk during an
ordinary day. Adding a format means adding a module here and one entry to the
two tables below. A file whose shape only its own script knows is handled
instead by calling ``register_reader``.
"""

from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any, TypeVar

from squeegee.errors import FormatError
from squeegee.io import csv_io, json_io, text_io

Record = dict[str, Any]
Resolved = TypeVar("Resolved")

_READERS = {
    ".csv": csv_io.read,
    ".json": json_io.read,
    ".jsonl": json_io.read,
    ".ndjson": json_io.read,
    ".txt": text_io.read,
    ".md": text_io.read,
}

# a reader a script registered for itself, which wins over the table above
_CUSTOM_READERS: dict[str, Callable[[Path], Iterator[Record]]] = {}

_WRITERS = {
    ".csv": csv_io.write,
    ".json": json_io.write_array,
    ".jsonl": json_io.write_lines,
    ".ndjson": json_io.write_lines,
}


def read_records(path: Path) -> Iterator[Record]:
    """Yield the records of ``path`` one at a time.

    Raises:
        FormatError: The extension is unsupported.
    """
    return reader_for(path)(path)


def write_records(path: Path, records: Iterable[Record]) -> int:
    """Write ``records`` to ``path`` and return how many were written.

    Raises:
        FormatError: The extension is unsupported.
    """
    return writer_for(path)(path, records)


def reader_for(path: Path) -> Callable[[Path], Iterator[Record]]:
    """Return the reader for ``path``, so a run can fail before it starts."""
    return _resolve({**_READERS, **_CUSTOM_READERS}, path)


def register_reader(suffix: str, reader: Callable[[Path], Iterator[Record]]) -> None:
    """Read ``suffix`` with ``reader`` for the rest of this run.

    A script calls this when its input has a shape no extension can imply, such
    as a text file whose entries are delimited by something only that file uses.
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
