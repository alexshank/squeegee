"""JSON reading and writing, for both a top-level array and JSON Lines."""

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from squeegee.errors import FormatError

Record = dict[str, Any]


def read_json(path: Path) -> Iterator[tuple[str, Record]]:
    """One record per element of a top-level array, or per line of JSON Lines."""
    if _starts_an_array(path):
        with path.open(encoding="utf-8") as handle:
            try:
                loaded = json.load(handle)
            except json.JSONDecodeError as error:
                raise FormatError(f"{path.name} is not valid JSON: {error}") from error
        for position, element in enumerate(loaded):
            if not isinstance(element, dict):
                raise FormatError(
                    f"{path.name} element {position} holds {type(element).__name__}, not an object"
                )
            # the parser keeps no offsets, so an element's raw text is re-serialized
            yield json.dumps(element, ensure_ascii=False), element
        return
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if line.strip():
                yield line.strip(), _object_from(line, path, number)


def write_json(path: Path, records: Iterable[Record]) -> Iterator[str]:
    """One element of a JSON array per record, yielding each as written."""
    with path.open("w", encoding="utf-8") as handle:
        handle.write("[")
        for number, record in enumerate(records):
            element = json.dumps(record, indent=2, ensure_ascii=False)
            # indented by hand, because the array is written one element at a time
            handle.write(("," if number else "") + "\n  " + element.replace("\n", "\n  "))
            yield element
        handle.write("\n]\n")


def write_json_lines(path: Path, records: Iterable[Record]) -> Iterator[str]:
    """One JSON object per line per record, yielding each as written."""
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            line = json.dumps(record, ensure_ascii=False)
            handle.write(line + "\n")
            yield line


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
