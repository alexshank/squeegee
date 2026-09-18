# Engineering Standards

These are set up before any implementation code is written, not after. An implementation agent that finds these tools missing should scaffold them first.

## Environment and packaging

- `uv` is the development environment manager: `uv sync` for the dev environment, `uv run` for every command below.
- `hatchling` is the build backend. `src/` layout, so tests import the installed package rather than the working directory.
- Python 3.11 is the floor. CI tests 3.11, 3.12, and 3.13.
- All tool configuration lives in `pyproject.toml`. No `setup.cfg`, no `.flake8`, no scattered config files.
- Both install paths are tested in CI: `pip install .` and `uvx --from . squeegee --help`.

## Formatting and linting

- `ruff format` is the only formatter. Line length 100.
- `ruff check` is the only linter. Enabled rule sets: `E`, `F`, `I` (import sorting), `N` (naming), `UP` (pyupgrade), `B` (bugbear), `A` (builtin shadowing), `C4`, `SIM`, `PTH`, `RUF`, and `D` for docstrings on public API only.
- Rule suppressions must be inline, narrow, and carry a reason: `# noqa: B008 - FastAPI dependency default`. Blanket per-file ignores need a comment explaining why.

## Typing

- `mypy --strict` over `src/` and `tests/`, with zero errors. This is a merge gate.
- No `Any` in the public API. Internal `Any` is allowed only where a JSON value is genuinely untyped, and `dict[str, Any]` for user records is the expected exception.
- No bare `# type: ignore`. Every ignore names its error code and has a reason comment.
- Third-party stubs are installed rather than ignored. If a dependency has no stubs at all, it gets a narrow `[[tool.mypy.overrides]]` block with a comment.
- Strict typing applies to this repository only. Squeegee imposes no typing requirements on the user scripts it runs, and must never fail a user's run over an annotation. See [technical-specification.md](technical-specification.md) for that contract.

## Testing

- `pytest`, with `pytest-cov`.
- Coverage gate: 90% line coverage on `src/squeegee/`, enforced with `--cov-fail-under=90` in CI. Coverage is a floor, not a target; an untested branch in the runner or the store is a defect regardless of the percentage.
- Tests mirror the source layout: `tests/test_stages.py`, `tests/test_runner.py`, `tests/store/test_sqlite.py`, and so on.
- Fixtures build real SQLite databases in `tmp_path`. The store is not mocked; its behaviour is the thing most worth testing.
- Required test cases, called out because they are the ones most likely to be skipped:
  - The append-only triggers actually fire: an `UPDATE` and a `DELETE` against each table raise.
  - A stage edited between two runs produces two `stage_versions` rows and the older run still resolves to the older source text.
  - A stage returning `None` records a drop, not an error, and later stages do not see the record.
  - A stage raising records the error and aborts the run by default, and the run still closes as `failed` with its partial results intact.
  - `--continue-on-error` records the failure and processes the remaining records.
  - A stage with no annotations at all registers and runs normally, and its stored annotation columns are NULL.
  - A value that cannot be serialized to JSON is still recorded, in the marker form.
- Property-based tests with `hypothesis` for the JSON round trip through the store are welcome but not required.

## Pre-commit

`.pre-commit-config.yaml` runs, in order, on every commit:

1. `ruff check --fix`
2. `ruff format`
3. `mypy --strict`
4. `check-yaml`, `check-toml`, `end-of-file-fixer`, `trailing-whitespace`, `check-merge-conflict`, `check-added-large-files`

Tests are not in pre-commit; they run in CI and on demand. Hooks should stay fast enough that nobody is tempted to use `--no-verify`.

## CI

GitHub Actions, on push and pull request:

- `lint`: ruff check, ruff format --check, mypy --strict.
- `test`: pytest with coverage across the supported Python versions on Ubuntu, plus one macOS and one Windows job because SQLite paths and file locking differ.
- `install`: verify `pip install .` and `uvx --from . squeegee --help` both work from a clean environment.
- Publishing to PyPI runs on tagged releases via trusted publishing. No API tokens in repository secrets.

## Practices

- Conventional Commits for commit messages.
- Small pull requests, each one leaving the repository green.
- Public functions and classes carry docstrings explaining why they exist; inline comments explain decisions, not mechanics.
- Errors aimed at the developer using Squeegee name the offending stage, file, or record, and suggest the fix. A stack trace with no context is a bug in the error handling.
- Dependencies are added reluctantly, and never to the core package. Every new dependency in the `ui` extra needs a sentence in the pull request explaining why it beats stdlib.
