"""Readers and writers, resolved by file extension.

Only CSV and JSON are supported, which covers what lands on a developer's
desk during an ordinary day. Adding a format means adding a module here and
one entry to the two tables below.
"""

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, TypeVar

from squeegee.errors import FormatError
from squeegee.io import csv_io, json_io

Record = dict[str, Any]
Resolved = TypeVar("Resolved")

_READERS = {
    ".csv": csv_io.read,
    ".json": json_io.read,
    ".jsonl": json_io.read,
    ".ndjson": json_io.read,
}

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
    return _resolve(_READERS, path)(path)


def write_records(path: Path, records: Iterable[Record]) -> int:
    """Write ``records`` to ``path`` and return how many were written.

    Raises:
        FormatError: The extension is unsupported.
    """
    return _resolve(_WRITERS, path)(path, records)


def _resolve(table: dict[str, Resolved], path: Path) -> Resolved:
    try:
        return table[path.suffix.lower()]
    except KeyError:
        supported = ", ".join(sorted(table))
        raise FormatError(
            f"cannot handle {path.name!r}: {path.suffix or 'no extension'} is not supported. "
            f"Supported extensions: {supported}"
        ) from None
