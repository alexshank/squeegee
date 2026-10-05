"""The example pipeline, run end to end.

These assertions are the numbers printed in docs/example-pipeline.md. If one
changes here, that document is wrong and needs the same edit.
"""

import csv
import io
import json
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from squeegee.cli import EXIT_OK, EXIT_RUN_FAILED, main
from squeegee.io import clear_readers
from squeegee.stages import clear_registry

EXAMPLES = Path(__file__).parents[1] / "examples"
SCRIPT = EXAMPLES / "clean_orders.py"


@pytest.fixture(autouse=True)
def _empty_registry() -> Iterator[None]:
    clear_registry()
    clear_readers()
    yield
    clear_registry()
    clear_readers()


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
    # the last stage returns CSV text, and nested fields travel through it as JSON
    assert cleaned[1] == {
        "order_id": "1003",
        "placed_on": "2026-09-02",
        "items": '[{"sku": "laptop", "quantity": 1}]',
        "amount_cents": "129900",
        "customer": '{"email": "grace@example.com", "domain": "example.com"}',
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
    assert "failed at stage 3 (parse_amount), record 8" in captured.err
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


def test_the_example_cleans_the_2022_words_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[dict[str, Any]] = []

    # the classifier is a paid network call, so the test answers in its place
    def fake_jev(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        asked.append(json.loads(request.data))  # type: ignore[arg-type]
        answer = {"type": "choice", "choice": "tv", "confidence": 0.9}
        return io.BytesIO(json.dumps({"answers": {"medium": answer}}).encode())

    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr(urllib.request, "urlopen", fake_jev)
    output = tmp_path / "words.json"

    exit_code = main(
        [
            "run",
            str(EXAMPLES / "words_2022.py"),
            "--input",
            str(EXAMPLES / "words-2022.txt"),
            "--output",
            str(output),
            "--db",
            str(tmp_path / "squeegee.db"),
        ]
    )

    assert exit_code == EXIT_OK
    entries = json.loads(output.read_text())
    # 75 blocks in: the file's title is a record of its own, dropped by the first stage
    assert len(entries) == 74
    assert entries[0]["date"] == "2022-01-01"
    assert entries[0]["quotes"][0]["source"] == "big lewbowski"
    # an entry whose quote runs across a blank line stays one record
    assert _entry_for("2022-11-17", entries)["quotes"] == [
        {
            "text": "As you are, so I once was As I am, so you will be",
            "source": "St. Catherine\u2019s crypt. Memento mori",
            "medium": "tv",
            "medium_confidence": 0.9,
        }
    ]
    # the one day two quotes were written down
    assert _entry_for("2022-11-21", entries)["quote_count"] == 2
    # the days written down without quote marks are kept, not dropped
    assert _entry_for("2022-01-10", entries)["quotes"] == [
        {
            "text": "THE DAWGS",
            "source": "crazy Georgia fan",
            "medium": "tv",
            "medium_confidence": 0.9,
        }
    ]
    # one question per quote, and the two-quote day asks twice
    assert len(asked) == 76
    assert asked[0]["state"].endswith("- big lewbowski")


def _entry_for(date: str, entries: list[dict[str, Any]]) -> dict[str, Any]:
    return next(entry for entry in entries if entry["date"] == date)
