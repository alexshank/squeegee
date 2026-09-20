"""The ``squeegee`` command.

argparse, no third-party CLI library, because the core package carries no
runtime dependencies.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from squeegee import __version__
from squeegee.errors import SqueegeeError
from squeegee.runner import RunResult, run
from squeegee.stages import clear_registry
from squeegee.store import list_runs, run_summary

DEFAULT_DATABASE = Path(".squeegee") / "squeegee.db"

EXIT_OK = 0
EXIT_RUN_FAILED = 1
EXIT_USAGE = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command named by ``argv`` and return a process exit code."""
    arguments = _parser().parse_args(argv)
    try:
        handler: Any = arguments.handler
        return int(handler(arguments))
    except SqueegeeError as error:
        print(f"squeegee: {error}", file=sys.stderr)
        return EXIT_USAGE


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="squeegee", description=__doc__)
    parser.add_argument("--version", action="version", version=f"squeegee {__version__}")
    subcommands = parser.add_subparsers(dest="command", required=True)

    runner = subcommands.add_parser("run", help="run a script over an input file")
    runner.add_argument("script", type=Path)
    runner.add_argument("--input", type=Path, required=True)
    runner.add_argument("--output", type=Path)
    runner.add_argument("--db", type=Path, help=f"defaults to {DEFAULT_DATABASE} beside the script")
    runner.add_argument("--limit", type=int, help="process only the first N records")
    runner.add_argument("--sample", type=int, help="process a random sample of N records")
    runner.add_argument("--seed", type=int, help="make --sample reproducible")
    runner.add_argument(
        "--continue-on-error",
        action="store_true",
        help="record stage errors and keep going; the default stops at the first one",
    )
    runner.add_argument("--quiet", action="store_true")
    runner.set_defaults(handler=_run)

    listing = subcommands.add_parser("runs", help="list recorded runs, newest first")
    listing.add_argument("--db", type=Path, default=DEFAULT_DATABASE)
    listing.add_argument("--limit", type=int, default=20)
    listing.set_defaults(handler=_runs)

    show = subcommands.add_parser("show", help="show one run and its stages")
    show.add_argument("run_id", type=int)
    show.add_argument("--db", type=Path, default=DEFAULT_DATABASE)
    show.set_defaults(handler=_show)

    ui = subcommands.add_parser("ui", help="open the local read-only explorer")
    ui.add_argument("--db", type=Path, default=DEFAULT_DATABASE)
    ui.add_argument("--port", type=int, default=8765)
    ui.set_defaults(handler=_ui)

    return parser


def _run(arguments: argparse.Namespace) -> int:
    script = arguments.script.resolve()
    _import_script(script)
    result = run(
        script_path=script,
        input_path=arguments.input,
        output_path=arguments.output,
        database_path=arguments.db or script.parent / DEFAULT_DATABASE,
        limit=arguments.limit,
        sample=arguments.sample,
        seed=arguments.seed,
        continue_on_error=arguments.continue_on_error,
    )
    if not arguments.quiet:
        _print_result(result)
    return EXIT_RUN_FAILED if result.status == "failed" else EXIT_OK


def _print_result(result: RunResult) -> None:
    if result.failure is not None:
        failure = result.failure
        print(
            f"run {result.run_id} failed at stage {failure.stage_position} "
            f"({failure.stage_name}), record {failure.record_index}: "
            f"{failure.error_type}: {failure.error_message}",
            file=sys.stderr,
        )
    # a failed run writes no output file, so "out" means "reached the last stage"
    outcome = "reached the last stage" if result.failure is not None else "out"
    print(
        f"run {result.run_id} {result.status}: {result.records_in} in, "
        f"{result.records_out} {outcome}, {result.records_dropped} dropped, "
        f"{result.records_errored} errored, {result.duration_us / 1_000_000:.2f}s"
    )
    print(f"recorded in {result.database_path}")


def _runs(arguments: argparse.Namespace) -> int:
    runs = list_runs(arguments.db, arguments.limit)["items"]
    if not runs:
        print(f"no runs recorded in {arguments.db}")
        return EXIT_OK
    for entry in runs:
        print(
            f"{entry['run_id']:>5}  {entry['status']:<9} {entry['started_at']}  "
            f"{Path(entry['script_path']).name}  {entry['records_in']} in, "
            f"{entry['records_out']} out, {entry['records_dropped']} dropped, "
            f"{entry['records_errored']} errored"
        )
    return EXIT_OK


def _show(arguments: argparse.Namespace) -> int:
    summary = run_summary(arguments.db, arguments.run_id)
    print(f"run {summary['run_id']}  {summary['status']}  {summary['script_path']}")
    print(f"  input  {summary['input_path']}")
    print(f"  output {summary['output_path'] or '(none)'}")
    print(
        f"  {summary['records_in']} in, {summary['records_out']} out, "
        f"{summary['records_dropped']} dropped, {summary['records_errored']} errored"
    )
    for stage in summary["stages"]:
        print(
            f"  {stage['position']:>2}  {stage['name']:<24} "
            f"{stage['records_in']:>6} in  {stage['records_ok']:>6} ok  "
            f"{stage['records_dropped']:>4} dropped  {stage['records_errored']:>3} errored"
        )
    if summary["failure"] is not None:
        failure = summary["failure"]
        print(
            f"  failed in stage {failure['stage_position']} ({failure['stage_name']}) "
            f"on record {failure['record_index']}: "
            f"{failure['error_type']}: {failure['error_message']}"
        )
    return EXIT_OK


def _ui(arguments: argparse.Namespace) -> int:
    # the server is slice 7; saying so is better than a stack trace
    raise SqueegeeError(
        "the ui is not built yet. Until it is, `squeegee runs` and `squeegee show RUN_ID` "
        f"read the same database ({arguments.db})"
    )


def _import_script(script: Path) -> None:
    if not script.is_file():
        raise SqueegeeError(f"script {script} does not exist")
    clear_registry()
    # the script's own directory goes first, so it can import its neighbours
    sys.path.insert(0, str(script.parent))
    specification = importlib.util.spec_from_file_location(script.stem, script)
    if specification is None or specification.loader is None:  # pragma: no cover - unreachable
        raise SqueegeeError(f"cannot import {script}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[script.stem] = module
    specification.loader.exec_module(module)


if __name__ == "__main__":  # pragma: no cover - exercised through the console script
    raise SystemExit(main())
