# 0001. SQLite over DuckDB for the store

- Status: accepted
- Date: 2026-09-18

## Context

Squeegee persists every stage input and output of every run to a local, append-only, embedded database. DuckDB is the obvious alternative to SQLite: it is also embedded and single-file, it is far better at analytics, and the UI's field statistics are analytical queries. The question is whether the analytics story justifies switching the store.

The workload has a specific shape: a run writes N record rows and up to N×S record event rows one at a time as records stream through the pipeline, and the UI later reads them back with filters and aggregates. A typical run is ten thousand records through five stages, roughly fifty thousand event rows.

## Decision

The store is SQLite, through the standard library `sqlite3` module. DuckDB is not a runtime dependency of the core package.

## Rationale

1. **Append-only needs triggers.** SQLite enforces the append-only rule structurally: a `BEFORE UPDATE` and `BEFORE DELETE` trigger per table that calls `RAISE(ABORT)`. DuckDB has no triggers, so append-only would degrade from an enforced guarantee to a convention that any future code path could break by accident. The guarantee is a headline property of the design.
2. **The UI must read while a run writes.** SQLite in WAL mode supports many concurrent readers alongside one writer, across processes. DuckDB takes an exclusive lock on the database file for the writing process; another process cannot open it, even read-only, while that writer holds it. Watching a run progress in the UI would be impossible.
3. **The write pattern is transactional, not analytical.** Squeegee inserts single rows continuously. That is SQLite's strength and DuckDB's weak path; DuckDB wants bulk appends into columnar storage.
4. **The core package must stay dependency-free.** `uvx squeegee` should start cold almost instantly, which rules out a tens-of-megabytes wheel for the core. `sqlite3` ships with Python.
5. **The analytical advantage does not apply at this size.** Fifty thousand rows aggregated with `json_extract` is a few milliseconds in SQLite. Columnar execution starts to matter in the millions.
6. **Archived runs should stay readable.** The database is an append-only record intended to be reviewable long after the run. SQLite's file format has a long-term stability guarantee; DuckDB's storage format has changed across releases, which would make an old database need a matching old DuckDB.

## Consequences

- Field statistics are written as SQLite aggregates over `json_extract`, including hand-rolled median and percentile queries that DuckDB would provide natively.
- The store layer is written against a narrow internal interface, so the engine is replaceable if the reasoning above stops holding.

## Where DuckDB may still be used later

Both of these are additive, in optional extras, and leave the store untouched.

- **Analytics acceleration in the UI.** DuckDB's `sqlite_scanner` reads a SQLite file directly, which would provide quantiles, `SUMMARIZE`, and histogram helpers without moving any data.
- **Additional input formats.** Parquet, Excel, and remote files are all natively readable by DuckDB, which beats writing readers by hand if Squeegee grows past CSV and JSON.

## Revisit when

- Field analytics in the UI become visibly slow, or
- Runs routinely exceed roughly one million `record_events` rows.
