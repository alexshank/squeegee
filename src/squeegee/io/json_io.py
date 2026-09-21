"""JSON reading and writing, for both a top-level array and JSON Lines."""

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from squeegee.errors import FormatError

Record = dict[str, Any]


def read(path: Path) -> Iterator[Record]:
    """Yield records from either a top-level array or one JSON object per line."""
    if _starts_an_array(path):
        with path.open(encoding="utf-8") as handle:
            loaded = json.load(handle)
        for position, element in enumerate(loaded):
            if not isinstance(element, dict):
                raise FormatError(
                    f"{path.name} element {position} holds {type(element).__name__}, not an object"
                )
            yield element
        return
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if line.strip():
                yield _object_from(line, path, number)


def write_array(path: Path, records: Iterable[Record]) -> int:
    """Write records as one JSON array."""
    materialized = list(records)
    path.write_text(json.dumps(materialized, indent=2) + "\n", encoding="utf-8")
    return len(materialized)


def write_lines(path: Path, records: Iterable[Record]) -> int:
    """Write records as JSON Lines, one object per line."""
    written = 0
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
            written += 1
    return written


def _starts_an_array(path: Path) -> bool:
    # the file is opened twice rather than rewound, because seeking a text stream to
    # anything but an opaque cookie is not defined
    with path.open(encoding="utf-8") as handle:
        while (character := handle.read(1)) != "":
            if not character.isspace():
                return character == "["
    return False


def _object_from(line: str, path: Path, number: int) -> Record:
    try:
        loaded = json.loads(line)
    except json.JSONDecodeError as error:
        raise FormatError(f"{path.name} line {number} is not valid JSON: {error}") from error
    if not isinstance(loaded, dict):
        raise FormatError(f"{path.name} line {number} holds {type(loaded).__name__}, not an object")
    return loaded
