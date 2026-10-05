"""Reading a plain text file as records, for the notes a person kept by hand.

A text file has no header row to name its fields, so a record here is only the
raw block and the line it began on. Turning that block into fields is the
pipeline's job, which keeps every parsing step visible in the run.
"""

import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

Record = dict[str, Any]


def read_text(path: Path) -> Iterator[tuple[str, Record]]:
    """One record per blank-line separated block of text."""
    return _blocks(path, lambda line: not line.strip(), keep_the_boundary=False)


def blocks_starting_with(pattern: str) -> Callable[[Path], Iterator[tuple[str, Record]]]:
    """Return a reader that starts a new record at every line matching ``pattern``.

    Blank lines belong to the block they fall inside, so an entry running over
    several paragraphs stays one record. Text before the first match is yielded
    as its own record rather than dropped, so nothing leaves the file unseen.
    """
    start = re.compile(pattern)

    def read_blocks(path: Path) -> Iterator[tuple[str, Record]]:
        """One record per block of text starting at a line that matches the pattern."""
        return _blocks(path, lambda line: start.match(line) is not None)

    return read_blocks


def _blocks(
    path: Path, is_a_boundary: Callable[[str], bool], keep_the_boundary: bool = True
) -> Iterator[tuple[str, Record]]:
    line_number = 1
    held: list[str] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if is_a_boundary(line):
            yield from _record(line_number, held)
            line_number, held = number, ([line] if keep_the_boundary else [])
            continue
        if not held:
            line_number = number
        held.append(line)
    yield from _record(line_number, held)


def _record(line_number: int, held: list[str]) -> Iterator[tuple[str, Record]]:
    text = "\n".join(held).strip()
    if text:
        yield text, {"line_number": line_number, "text": text}
