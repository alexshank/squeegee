"""Tests for the command line interface."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from squeegee.cli import EXIT_OK, EXIT_RUN_FAILED, EXIT_USAGE, main
from squeegee.stages import clear_registry
from squeegee.store import Store

SCRIPT = '''
from squeegee import stage


@stage
def drop_the_second(record):
    """Drop one record so the counts are interesting."""
    return None if record["id"] == "2" else record


@stage
def fail_on_the_third(record):
    if record["id"] == "3":
        raise ValueError("bad row")
    return record
'''


@pytest.fixture(autouse=True)
def _empty_registry() -> Iterator[None]:
    clear_registry()
    yield
    clear_registry()


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "clean.py").write_text(SCRIPT)
    (tmp_path / "orders.csv").write_text("id\n1\n2\n3\n")
    return tmp_path


def run_cli(workspace: Path, *arguments: str) -> int:
    return main([*arguments, "--db", str(workspace / "squeegee.db")])


def run_script(workspace: Path) -> int:
    return run_cli(
        workspace,
        "run",
        str(workspace / "clean.py"),
        "--input",
        str(workspace / "orders.csv"),
    )


def test_a_successful_run_reports_its_counts(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (workspace / "orders.csv").write_text("id\n1\n2\n")

    exit_code = run_cli(
        workspace,
        "run",
        str(workspace / "clean.py"),
        "--input",
        str(workspace / "orders.csv"),
        "--output",
        str(workspace / "clean.csv"),
    )

    assert exit_code == EXIT_OK
    assert "2 in, 1 out, 1 dropped, 0 errored" in capsys.readouterr().out


def test_a_failed_run_exits_non_zero_and_names_the_stage(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = run_script(workspace)

    captured = capsys.readouterr()
    assert exit_code == EXIT_RUN_FAILED
    assert "failed at stage 1 (fail_on_the_third), record 2" in captured.err
    assert "ValueError: bad row" in captured.err


def test_quiet_prints_nothing_on_success(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (workspace / "orders.csv").write_text("id\n1\n")

    run_cli(
        workspace,
        "run",
        str(workspace / "clean.py"),
        "--input",
        str(workspace / "orders.csv"),
        "--quiet",
    )

    assert capsys.readouterr().out == ""


def test_runs_lists_what_has_been_recorded(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_script(workspace)
    capsys.readouterr()

    assert run_cli(workspace, "runs") == EXIT_OK
    listed = capsys.readouterr().out
    assert "failed" in listed
    assert "clean.py" in listed


def test_show_prints_every_stage(workspace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_script(workspace)
    capsys.readouterr()

    assert run_cli(workspace, "show", "1") == EXIT_OK
    shown = capsys.readouterr().out
    assert "drop_the_second" in shown
    assert "failed in stage 1 (fail_on_the_third) on record 2" in shown


def test_show_of_an_unknown_run_is_a_usage_error(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_script(workspace)
    capsys.readouterr()

    assert run_cli(workspace, "show", "99") == EXIT_USAGE
    assert "no run 99" in capsys.readouterr().err


def test_runs_against_a_missing_database_says_so(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_cli(workspace, "runs") == EXIT_USAGE
    assert "no squeegee database" in capsys.readouterr().err


def test_a_missing_script_is_a_usage_error(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = run_cli(
        workspace, "run", str(workspace / "absent.py"), "--input", str(workspace / "orders.csv")
    )

    assert exit_code == EXIT_USAGE
    assert "does not exist" in capsys.readouterr().err


def test_the_ui_refuses_a_database_that_does_not_exist(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_cli(workspace, "ui") == EXIT_USAGE
    assert "no squeegee database" in capsys.readouterr().err


def test_the_ui_serves_the_database_it_was_given(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    Store(workspace / "squeegee.db").close()
    served: dict[str, object] = {}

    def record(database: Path, port: int) -> int:
        served.update(database=database, port=port)
        return EXIT_OK

    monkeypatch.setattr("squeegee.ui.serve", record)

    assert run_cli(workspace, "ui", "--port", "9999") == EXIT_OK
    assert served == {"database": workspace / "squeegee.db", "port": 9999}


def test_the_database_defaults_to_beside_the_script(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (workspace / "orders.csv").write_text("id\n1\n")

    main(["run", str(workspace / "clean.py"), "--input", str(workspace / "orders.csv")])

    assert (workspace / ".squeegee" / "squeegee.db").is_file()
    assert ".squeegee/squeegee.db" in capsys.readouterr().out


def test_an_empty_database_lists_nothing(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    Store(workspace / "squeegee.db").close()

    assert run_cli(workspace, "runs") == EXIT_OK
    assert "no runs recorded" in capsys.readouterr().out


def test_a_limit_below_one_is_a_usage_error(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    Store(workspace / "squeegee.db").close()

    assert run_cli(workspace, "runs", "--limit", "0") == EXIT_USAGE
    assert "limit must be at least 1" in capsys.readouterr().err
