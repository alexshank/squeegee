"""CSV reading and writing."""

import csv
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from squeegee.errors import FormatError

Record = dict[str, Any]


def read(path: Path) -> Iterator[Record]:
    """Yield one record per row, keyed by the header."""
    with path.open(newline="", encoding="utf-8") as handle:
        yield from csv.DictReader(handle)


def write(path: Path, records: Iterable[Record]) -> int:
    """Write records as CSV, taking the column set from the first record."""
    written = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer: csv.DictWriter[str] | None = None
        for record in records:
            if writer is None:
                writer = csv.DictWriter(handle, fieldnames=list(record))
                writer.writeheader()
            elif set(record) != set(writer.fieldnames):
                # writing anyway would silently drop the columns the header lacks
                raise FormatError(
                    f"record {written} has fields {sorted(record)}, but the CSV header is "
                    f"{sorted(writer.fieldnames)}; every record must have the same fields"
                )
            writer.writerow(record)
            written += 1
    return written
