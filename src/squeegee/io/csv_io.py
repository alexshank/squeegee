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


def write_csv(path: Path, records: Iterable[Record | str]) -> Iterator[str]:
    """One CSV row per record under a header taken from the first, yielding each as written.

    A record may also be CSV text with its own header, as a stage that renders
    CSV returns, which is read back into rows rather than written verbatim.
    """
    fieldnames: list[str] = []
    header = ""
    written = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        for record in records:
            rows = _rows(record)
            if not header:
                fieldnames = list(rows[0])
                # a header is the row whose values are its own names
                header = _csv_text(fieldnames, [dict(zip(fieldnames, fieldnames, strict=True))])
                handle.write(header)
            for row in rows:
                if set(row) != set(fieldnames):
                    # writing anyway would silently drop the columns the header lacks
                    raise FormatError(
                        f"row {written} has fields {sorted(row)}, but the CSV header is "
                        f"{sorted(fieldnames)}; every record must have the same fields"
                    )
                written += 1
            body = _csv_text(fieldnames, rows)
            handle.write(body)
            # like a read row, a written one carries the header, so it reads on its own
            yield (header + body).rstrip("\r\n")


def _csv_text(fieldnames: list[str], rows: list[Record]) -> str:
    text = io.StringIO()
    csv.DictWriter(text, fieldnames=fieldnames).writerows(rows)
    return text.getvalue()


def _rows(record: Record | str) -> list[Record]:
    if not isinstance(record, str):
        return [record]
    rows = list(csv.DictReader(io.StringIO(record)))
    if not rows:
        # a lone line reads as a header with no rows, and the record would vanish
        raise FormatError(f"CSV text {record[:40]!r} has a header but no rows")
    return rows
