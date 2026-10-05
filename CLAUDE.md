# Squeegee

Observable data cleaning: a Python script of `@stage` functions runs one record at a time, every stage's input and output lands in an append-only SQLite store, and a local React UI explores the run.

- Python package: `src/squeegee/` (stdlib only at runtime). UI: `frontend/` (React + Vite, built into the package).
- Design docs live in `docs/` (start at `docs/README.md`); read the relevant one before changing behavior, and update it with the change.

## Commands

```
uv sync                 # environment
make check              # ruff, mypy, pytest (90% coverage gate)
make ui                 # build frontend into the package
make ui-check           # biome, tsc, vitest
uv run squeegee run examples/clean_orders.py --input examples/orders.csv -n 5
uv run squeegee ui      # --db defaults to /tmp/squeegee.db
```
