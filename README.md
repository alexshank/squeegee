# Squeegee

Observable cleaning and transforming of small data, for the ad-hoc work that lands on a developer during a normal day.

You already write the throwaway script. Squeegee records what it did, so that when a value comes out wrong you can see which step did it.

> **Status: early.** Stages, readers and writers, the append-only store, the runner, and the CLI work today, and [`examples/`](examples/) runs end to end. The read-only web UI does not exist yet, so `squeegee ui` says so and points at `squeegee runs` and `squeegee show` instead. Progress is tracked in [docs/implementation-plan.md](docs/implementation-plan.md).

## The idea

Write an ordinary Python script where each transformation is one decorated function:

```python
from squeegee import stage

@stage
def normalize_headers(record):
    """Lowercase and underscore every column name."""
    return {key.strip().lower().replace(" ", "_"): value for key, value in record.items()}

@stage
def parse_amount(record):
    """Convert the amount column from a currency string to cents."""
    record["amount_cents"] = round(float(record.pop("amount").lstrip("$")) * 100)
    return record

@stage
def drop_test_rows(record):
    """Return None to drop a record from the rest of the pipeline."""
    return None if record["email"].endswith("@internal.test") else record
```

Run it through the CLI:

```
squeegee run clean_orders.py --input orders.csv --output clean.csv
```

Stages run in declaration order, one record at a time. Every intermediate input and output is written to a local, append-only SQLite database. Then:

```
squeegee ui
```

opens a local, read-only page where you can see how many records each stage dropped, trace a single record through every stage, read the source of the stage that touched it, and check field statistics before and after a transformation.

## What it is not

Not a scheduler, not an orchestrator, not a warehouse tool. If the data matters to the business every day, you have outgrown Squeegee. It is for the CSV a colleague sent you an hour ago.

## Design

| Document | Contents |
| --- | --- |
| [docs/product-requirements.md](docs/product-requirements.md) | Problem, audience, scope, success criteria |
| [docs/technical-specification.md](docs/technical-specification.md) | Public API, stage contract, execution model, CLI |
| [docs/data-model.md](docs/data-model.md) | ERD, SQLite schema, append-only rules, stage versioning |
| [docs/api.md](docs/api.md) | The read-only HTTP API behind the UI |
| [docs/ui-specification.md](docs/ui-specification.md) | Screens, code display, the hand-written server checklist |
| [docs/engineering-standards.md](docs/engineering-standards.md) | Linting, typing, testing, pre-commit, CI |
| [docs/decisions/](docs/decisions/) | Why SQLite and not DuckDB; why a stdlib server and not FastAPI |
| [docs/ui-wireframes/](docs/ui-wireframes/) | Black and white wireframes, five UX approaches |
| [docs/example-pipeline.md](docs/example-pipeline.md) | The worked example in `examples/`, and how to use it for validation |

Decisions worth knowing before reading the rest: stages take one record at a time, pipelines are declaration order, the store is append-only SQLite, runs fail fast, and the package has no third-party runtime dependencies.

Squeegee itself is strictly typed and strictly linted. **Your** scripts are not: annotations on stage functions are optional, and Squeegee will never fail your run over one.

## Development

```
uv sync      # create the environment
make hooks   # install the pre-commit hooks
make check   # lint, typecheck, test
```

Every check runs locally. There is no CI, deliberately; see [docs/engineering-standards.md](docs/engineering-standards.md).

## License

MIT
