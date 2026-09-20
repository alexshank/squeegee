# Implementation Plan

Ordered, independently shippable slices. Each one is a task-sized unit for a single implementing agent: it names the files it owns, what done means, and what it must not touch. A slice is finished when `make check` passes and its acceptance criteria hold.

Read [technical-specification.md](technical-specification.md) and [data-model.md](data-model.md) before starting any slice. Where this plan and a specification disagree, the specification wins, and the disagreement is worth raising rather than resolving quietly.

## Rules for every slice

- `make check` passes: ruff, `mypy --strict`, pytest with the 90% coverage floor.
- No slice adds a third-party runtime dependency. Dev and frontend build dependencies are fine.
- No slice weakens the append-only rule, the fail-fast default, or the "user scripts need no annotations" contract.
- Tests live beside the slice and use real SQLite databases in `tmp_path`. The store is never mocked.
- Errors aimed at a developer name the stage, file, or record, and say what to do.

## Slice 0 — Toolchain (done)

Packaging, ruff, mypy, pytest, pre-commit, Makefile. Checks run locally; there is no CI.

## Slice 1 — Stage registry (done)

**Files:** `src/squeegee/stages.py`, `tests/test_stages.py`

Implement the `@stage` decorator and the module-level registry.

- Works bare and called: `@stage`, `@stage(name=..., description=...)`.
- Returns the original function unchanged, so a script's functions stay directly callable and unit-testable.
- Captures, per stage: name, description defaulting to the first docstring line, dedented source text, SHA-256 of that source, and the parameter and return annotations as text, each `None` when absent.
- Registry preserves declaration order and can be cleared, which the tests need.
- Rejects, before any run: a function taking other than exactly one positional parameter, a generator function, and an `async def`. Each error names the offending stage.

**Acceptance:** a module with three decorated functions yields three registry entries in declaration order, with correct hashes; an unannotated stage registers with `None` annotations; the three rejected shapes raise with the stage name in the message.

**Not in this slice:** execution, persistence, type compatibility checking of any kind.

## Slice 2 — Readers and writers (done)

**Files:** `src/squeegee/io/`, `tests/test_io.py`

- `read(path)` yields records one at a time; `write(path, records)` consumes an iterable.
- CSV through `csv.DictReader` and `csv.DictWriter`; JSON supporting both a top-level array and JSON Lines, detected by inspecting the first non-whitespace character.
- Resolution by file extension, with an unknown extension raising before any record is read, naming the extension and listing the supported ones.
- Writers derive their column set from the first record and raise a clear error if a later record has different keys, rather than silently dropping columns.

**Acceptance:** round trip of CSV and of both JSON shapes preserves records; an unknown extension fails before opening the file; reading is streaming, which a test asserts by reading one record from a large file without exhausting it.

## Slice 3 — Append-only store (done)

**Files:** `src/squeegee/store/`, `tests/store/test_sqlite.py`

The schema exactly as written in [data-model.md](data-model.md), including the `UPDATE` and `DELETE` triggers on every table and the `run_status` view. WAL mode on. Write side only in this slice.

- A narrow `Store` interface: open or create a database, start a run, register stage versions, record a record, record record events in batches, close a run by inserting a `run_event`.
- Stage version reuse: the same name and source hash resolves to the existing row rather than inserting a duplicate.
- Values are stored as JSON text. A value that cannot be serialized is stored as `{"__squeegee_unserializable__": "<repr>"}` and the event is still written.
- Event writes are batched in transactions rather than one transaction per event.

**Acceptance:** an `UPDATE` and a `DELETE` against every table raises; a run recorded then closed is reported correctly by `run_status`; the same stage across two runs produces one `stage_versions` row and an edited stage produces two, with the older run still resolving to the older source text; an unserializable value is recorded in the marker form.

## Slice 4 — Runner (done)

**Files:** `src/squeegee/runner.py`, `tests/test_runner.py`

Drives records through the registered stages and records everything.

- Streams records; each stage receives a deep copy of the record so the stored input is the true input even if a stage mutates in place.
- Returning `None` records a `dropped` event and stops that record; later stages never see it.
- A raising stage records an `error` event with type, message, and traceback, then aborts the run, which closes as `failed` with its partial results intact. `continue_on_error=True` instead proceeds to the next record.
- Wiring failures happen before any record is processed: no stages registered, unknown file extension, unreadable input.
- Surviving records go to the writer. `--limit`, `--sample`, and `--seed` are honoured here.

**Acceptance:** the drop, error, and fail-fast behaviours each assert against both the output file and the stored events; a stage mutating its input in place does not corrupt the stored input; a run over ten thousand records through five stages completes in under five seconds with persistence on.

## Slice 5 — CLI (done, except `ui`)

**Files:** `src/squeegee/cli.py`, `tests/test_cli.py`, and uncommenting `[project.scripts]` in `pyproject.toml`

`argparse`, no third-party CLI library. Subcommands `run`, `runs`, `show`, and `ui`, with the flags in the technical specification. Imports the user's script by path, which triggers registration.

- The run summary prints run id, counts, elapsed time, and the database path.
- A failed run prints the failing stage, record index, and exception, and exits non-zero.
- `runs` and `show` are the terminal equivalents of the first two UI screens.

**Acceptance:** an end-to-end test runs a real script over a real CSV through the CLI and asserts the output file, the exit code, and the stored run; `pip install .` then `squeegee --help` works from a clean environment.

## Slice 6 — Query layer (done)

**Files:** `src/squeegee/store/queries.py`, `tests/store/test_queries.py`

Read-side functions backing every endpoint in [api.md](api.md), returning plain dictionaries. One function per endpoint, no HTTP awareness.

- Cursor pagination on the primary key, with capped page sizes.
- Per-stage counts and duration percentiles as SQL aggregates.
- Field statistics through `json_extract`, including hand-rolled median and percentile, plus histograms and top values.
- `changed_fields` computed server side by comparing each event's input and output at the top level.

**Acceptance:** each function is tested against a fixture database built by a real run; pagination returns every row exactly once across pages; field statistics match values computed independently in the test.

Every function is tested against the database that [example-pipeline.md](example-pipeline.md) describes, built by running the real example through the real CLI.

## Slice 7 — HTTP server

**Files:** `src/squeegee/ui/server.py`, `tests/ui/test_server.py`

`ThreadingHTTPServer` over the query layer. Every item in the hand-written server checklist in [ui-specification.md](ui-specification.md) is implemented and tested: explicit MIME types, `translate_path` reuse for static files, the single page fallback, daemon threads, per-thread read-only connections, `127.0.0.1` binding, a clear message on a busy port, one place for parameter validation, and the shared error envelope.

**Acceptance:** every documented endpoint returns its documented shape; a bad parameter returns 400 naming it; an unknown `/api` path returns JSON 404 while an unknown other path returns `index.html`; a test asserts that every route registered in the server appears in `docs/api.md`.

## Slice 8 — Frontend scaffold

**Files:** `frontend/`, plus the Hatch build hook in `pyproject.toml`

Vite, React, TypeScript in strict mode, Biome, Vitest. Builds into `src/squeegee/ui/static/`, which stays gitignored. The build hook fails a wheel build when the assets are missing. Ships the app shell, routing, the fetch layer typed against `docs/api.md`, and the CSS custom properties for light and dark.

**Acceptance:** `vite build` produces assets the server serves; `biome ci` and `tsc --noEmit` pass; a wheel built without the assets fails loudly.

## Slice 9 — UI screens

**Files:** `frontend/src/`

The screens from [ui-specification.md](ui-specification.md), in the layout chosen from [ui-wireframes/](ui-wireframes/): runs list, run overview, stage detail, record trace, field analytics. Includes the code display rules, Lucide icons imported individually, and status shown by more than colour.

**Acceptance:** each screen renders against a real database produced by a real run; the record trace highlights changed fields; the failure banner leads on a failed run.

## Slice 10 — Release

**Files:** `pyproject.toml`, `README.md`, `docs/`

Version, classifiers, a manual release checklist, and the two clean-environment checks run by hand: `pip install .` then `import squeegee`, and `uvx --from . squeegee --help`. Publishing to PyPI is manual until CI exists.

## Dependency order

Slices 1, 2, and 3 are independent of one another and can be worked in parallel. Slice 4 needs all three. Slice 5 needs 4. Slice 6 needs 3. Slice 7 needs 6. Slice 8 is independent of everything on the Python side. Slice 9 needs 7 and 8. Slice 10 is last.
