"""CSV reading and writing."""

import csv
import io
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from squeegee.errors import FormatError

Record = dict[str, Any]


def read_csv(path: Path) -> Iterator[tuple[str, Record]]:
    """One record per CSV row, keyed by the header row, which each raw slice repeats."""
    with path.open(newline="", encoding="utf-8") as handle:
        consumed: list[str] = []

        def lines() -> Iterator[str]:
            for line in handle:
                consumed.append(line)
                yield line

        reader = csv.DictReader(lines())
        # the header is read first, so it is never mistaken for part of a row
        if reader.fieldnames is None:
            return
        header = "".join(consumed).rstrip("\r\n")
        consumed.clear()
        for row in reader:
            # a row alone is a list of values with no names, so its raw text carries the
            # header too; a quoted field may span lines, so the row is every line consumed
            # blank lines before a row are skipped by the reader, so they are trimmed here too
            yield f"{header}\n" + "".join(consumed).strip("\r\n"), row
            consumed.clear()


def write(path: Path, records: Iterable[Record | str]) -> int:
    """Write records as CSV, taking the column set from the first, and count the rows.

    A record may also be CSV text with its own header, as a stage that renders
    CSV returns, which is read back into rows rather than written verbatim.
    """
    written = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer: csv.DictWriter[str] | None = None
        for record in (row for given in records for row in _rows(given)):
            if writer is None:
                writer = csv.DictWriter(handle, fieldnames=list(record))
                writer.writeheader()
            elif set(record) != set(writer.fieldnames):
                # writing anyway would silently drop the columns the header lacks
                raise FormatError(
                    f"row {written} has fields {sorted(record)}, but the CSV header is "
                    f"{sorted(writer.fieldnames)}; every record must have the same fields"
                )
            writer.writerow(record)
            written += 1
    return written


def _rows(record: Record | str) -> list[Record]:
    if not isinstance(record, str):
        return [record]
    rows = list(csv.DictReader(io.StringIO(record)))
    if not rows:
        # a lone line reads as a header with no rows, and the record would vanish
        raise FormatError(f"CSV text {record[:40]!r} has a header but no rows")
    return rows
