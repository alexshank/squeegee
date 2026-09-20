# Technical Specification

## Distribution

- Package name on PyPI: `squeegee` (verified unclaimed as of 2026-09-18).
- Build backend: `hatchling`. Source layout: `src/squeegee/`.
- Minimum Python: 3.11.
- Zero third-party runtime dependencies, including the UI, so `uvx squeegee` starts cold in well under a second and `uvx squeegee ui` needs nothing extra installed.
- React is a build-time dependency only. The wheel ships the built UI assets; users never need Node. See [decisions/0002-react-ui-on-a-stdlib-server.md](decisions/0002-react-ui-on-a-stdlib-server.md).
- Console entry point: `squeegee = "squeegee.cli:main"`.

## Package layout

```
src/squeegee/
    __init__.py        # public API: stage, run, __version__
    stages.py          # @stage decorator, registry, signature validation
    runner.py          # execution engine: drives records through stages
    io/
        __init__.py    # reader/writer resolution by file extension
        csv_io.py
        json_io.py
    store/
        __init__.py    # Store facade used by the runner
        schema.sql     # table and trigger definitions
        sqlite.py      # append-only SQLite implementation
    cli.py             # argument parsing and subcommands
    ui/
        server.py      # ThreadingHTTPServer: static assets plus read-only JSON API
        static/        # build output of frontend/, shipped in the wheel, gitignored in the repo
```

```
frontend/              # React sources, built by Vite into src/squeegee/ui/static/
    src/
    index.html
    package.json
```

## Public API

The public surface is deliberately tiny.

```python
from squeegee import stage

@stage
def parse_amount(record):
    """Convert the amount column from a currency string to cents."""
    ...

@stage(name="drop_internal_test_orders")
def drop_test_rows(record):
    """Return None to drop the record from the rest of the pipeline."""
    ...
```

Annotations are welcome and are shown in the UI when present, but they are never required:

```python
@stage
def parse_amount(record: dict[str, Any]) -> dict[str, Any]:
    ...
```

- `@stage` works bare or called with keyword arguments.
- `@stage(name=...)` overrides the stage name shown in the UI. Defaults to the function name.
- `@stage(description=...)` overrides the description. Defaults to the first line of the docstring.
- The decorator returns the original function unchanged, so the script's functions remain directly callable and unit-testable.

### Stage contract

- Exactly one positional parameter: the record.
- Type annotations are optional and never required. When present they are recorded and shown in the UI as documentation. Squeegee never rejects a stage for a missing, loose, or unusual annotation.
- The record type must be a mapping type: `dict[str, Any]`, a `TypedDict`, or a dataclass. Dataclasses are converted to and from dictionaries at the storage boundary.
- Returning `None` drops the record from the rest of the pipeline. No annotation is needed to enable this.
- A stage should not mutate its input in place. The runner passes each stage a deep copy of the record so that the stored "input" value is the true input even if a stage ignores this rule.
- Stages must not be generators and must not be `async def` in v1.

### Annotations are advisory

Squeegee does no static checking of user code. It does not compare stage N's return annotation against stage N+1's parameter annotation, and it does not validate a record against an annotation at runtime. Annotations are captured as text for display and nothing more. A genuine type mismatch between stages surfaces the ordinary way: the receiving stage raises, and fail-fast stops the run with that stage and record named.

This asymmetry is deliberate. Squeegee's own source is checked with `mypy --strict`; the user's script is checked by nothing.

## Execution model

1. The CLI imports the user's script as a module. Import triggers the decorators, which append to a module-level registry in declaration order.
2. The runner resolves the reader from the input file extension and the writer from the output file extension.
3. The runner opens the store, inserts a `runs` row, and inserts or reuses a `stage_versions` row for each registered stage.
4. Records stream one at a time. For each record the runner assigns a record index, then walks the stages in order. For each stage it writes one `record_events` row holding the input value, the output value, a status, and the elapsed time.
5. A stage returning `None` marks the record dropped. No later stage runs for that record.
6. A stage raising an exception marks the record errored and stores the exception type, message, and traceback. The run then aborts: fail fast is the default. The run is still closed out cleanly with status `failed`, so the partial results stay reviewable in the UI. With `--continue-on-error` the runner instead moves on to the next record and the run finishes normally.
7. Records surviving every stage are handed to the writer. A failed run writes no output file at all, because half a cleaned CSV is worse than none; the recorded run still holds everything that was processed.
8. The runner closes the `runs` row with an end timestamp, a status, and summary counts.

Execution is single process and synchronous. Persistence happens in batched transactions so a ten thousand record run does not pay one transaction per event.

### Stage versioning

Each stage version is identified by the SHA-256 of its dedented source text combined with its name. Editing a stage produces a new `stage_versions` row on the next run. Old runs keep pointing at the old row, so the UI can always show the exact code that produced a historical value. The source text itself is stored, which makes the database self-contained for review.

## CLI

```
squeegee run SCRIPT --input PATH [--output PATH] [options]
squeegee runs [--limit N]
squeegee show RUN_ID
squeegee ui [--port 8765]
```

### `squeegee run`

| Flag | Meaning |
| --- | --- |
| `--input PATH` | Input file. Required. Extension selects the reader. |
| `--output PATH` | Output file. Optional; omit to record a run without writing results. |
| `--db PATH` | Database file. Defaults to `.squeegee/squeegee.db` next to the script. |
| `--limit N` | Process only the first N records. |
| `--sample N` | Process a random sample of N records, with `--seed` for reproducibility. |
| `--continue-on-error` | Record stage exceptions and keep going. Default is to abort on the first one. |
| `--quiet` | Suppress the progress summary on stdout. |

On completion the CLI prints a short summary: run id, records in, records out, records dropped, records errored, elapsed time, and the database path.

### `squeegee runs` and `squeegee show`

Terminal equivalents of the UI's two main screens, so the tool stays useful without installing the UI extra. `show` prints per-stage counts for one run.

### `squeegee ui`

Starts the local server, binds to `127.0.0.1` only, and prints the URL. Serves the built React assets and the read-only JSON API from one `ThreadingHTTPServer`, with one `sqlite3` connection per thread, each opened read-only through a `file:...?mode=ro` URI.

## Error handling

- Wiring problems (no stages registered, unknown file extension, unreadable input, a stage taking the wrong number of parameters) fail before any record is processed, with a message naming the offending stage or file.
- Per-record failures abort the run by default, after being recorded. The developer sees the failure immediately rather than discovering it at the bottom of a summary. `--continue-on-error` trades that for a complete picture in one pass.
- The store is opened with `PRAGMA journal_mode=WAL` so the UI can read a database while a run writes to it.

## Performance targets

- Ten thousand records through five stages, including persistence, in under five seconds on a laptop.
- Memory use is bounded by the streaming design, not the input size, apart from the batching buffer.
