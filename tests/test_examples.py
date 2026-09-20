"""The example pipeline, run end to end.

These assertions are the numbers printed in docs/example-pipeline.md. If one
changes here, that document is wrong and needs the same edit.
"""

import csv
from collections.abc import Iterator
from pathlib import Path

import pytest

from squeegee.cli import EXIT_OK, EXIT_RUN_FAILED, main
from squeegee.stages import clear_registry

EXAMPLES = Path(__file__).parents[1] / "examples"
SCRIPT = EXAMPLES / "clean_orders.py"


@pytest.fixture(autouse=True)
def _empty_registry() -> Iterator[None]:
    clear_registry()
    yield
    clear_registry()


def test_the_example_cleans_the_example_orders(tmp_path: Path) -> None:
    output = tmp_path / "clean.csv"

    exit_code = main(
        [
            "run",
            str(SCRIPT),
            "--input",
            str(EXAMPLES / "orders.csv"),
            "--output",
            str(output),
            "--db",
            str(tmp_path / "squeegee.db"),
        ]
    )

    assert exit_code == EXIT_OK
    cleaned = list(csv.DictReader(output.open()))
    assert [record["order_id"] for record in cleaned] == [
        "1001",
        "1003",
        "1005",
        "1006",
        "1008",
        "1009",
    ]
    assert cleaned[1] == {
        "order_id": "1003",
        "email": "grace@example.com",
        "placed_on": "2026-09-02",
        "amount_cents": "129900",
    }


def test_the_bad_row_stops_the_run_and_writes_no_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "clean.csv"

    exit_code = main(
        [
            "run",
            str(SCRIPT),
            "--input",
            str(EXAMPLES / "orders_with_a_bad_row.csv"),
            "--output",
            str(output),
            "--db",
            str(tmp_path / "squeegee.db"),
        ]
    )

    assert exit_code == EXIT_RUN_FAILED
    assert not output.exists()
    captured = capsys.readouterr()
    assert "failed at stage 2 (parse_amount), record 8" in captured.err
    assert "could not convert string to float: 'n/a'" in captured.err
    assert "9 in, 4 reached the last stage, 4 dropped, 1 errored" in captured.out


def test_continuing_past_the_bad_row_finishes(tmp_path: Path) -> None:
    output = tmp_path / "clean.csv"

    exit_code = main(
        [
            "run",
            str(SCRIPT),
            "--input",
            str(EXAMPLES / "orders_with_a_bad_row.csv"),
            "--output",
            str(output),
            "--db",
            str(tmp_path / "squeegee.db"),
            "--continue-on-error",
        ]
    )

    assert exit_code == EXIT_OK
    assert [record["order_id"] for record in csv.DictReader(output.open())] == [
        "1001",
        "1003",
        "1005",
        "1006",
        "1009",
    ]
