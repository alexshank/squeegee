# Product Requirements

## Problem

Developers regularly receive small, messy data during ordinary work: a CSV export from a colleague, a JSON dump from an API, a spreadsheet saved by someone else. They clean it with a throwaway script, get an answer, and throw the script away. When the result looks wrong, there is no record of what the script did to any particular row, so the developer re-runs the script with print statements until the problem shows itself.

Squeegee makes that throwaway script observable without making it a production system.

## Audience

Working developers cleaning or reshaping small data as a side task. They know Python. They do not want to stand up Airflow, dbt, or a warehouse to fix a thousand-row CSV.

## What Squeegee is

A Python package, installable with both `pip` and `uv`, that lets a developer write an ordinary Python script where each transformation is one decorated function. Running that script through the Squeegee CLI records every intermediate input and output to a local SQLite database, and a local read-only web UI explores what happened.

## What Squeegee is not

- Not a scheduler or orchestrator. No cron, no retries, no DAGs, no distributed execution.
- Not for long-running or business-critical pipelines. If the data matters to the business every day, the user has outgrown Squeegee.
- Not a big data tool. Expected inputs are up to roughly a few hundred thousand records, single machine, single process.
- Not an editor. The UI never mutates data or re-runs pipelines.

## Core user journey

1. The developer writes `clean_orders.py` with several decorated functions, one per transformation step.
2. They run `squeegee run clean_orders.py --input orders.csv --output clean.csv`.
3. Squeegee runs each record through the stages in declaration order, writes the output file, and records every intermediate value in a local SQLite database.
4. Something looks off. They run `squeegee ui` and open the local web page.
5. They see the run overview: how many records entered, how many each stage dropped, how many errored.
6. They pick one suspicious record and see its value after each stage, so they can see exactly which stage changed it and how.
7. They check field-level statistics (counts, nulls, averages, sums, distinct values) before and after a stage to confirm the transformation did what they expected.

## Requirements

### Must have

- `@stage` decorator that registers a function as one step in the pipeline.
- Fail fast by default: the first stage exception aborts the run. The failing record, the stage, and the exception are recorded before the run closes as failed.
- No typing requirements on user scripts. Type annotations on stage functions are optional. When present they are recorded and shown in the UI as documentation; when absent nothing changes. The target user is writing a ten-minute cleaning script between two other tasks, and Squeegee must not add ceremony to that.
- CLI: run a script, inspect past runs, launch the UI.
- CSV and JSON input and output.
- Every stage input and output persisted to local SQLite, append-only.
- Re-running a script after editing a stage creates new records; prior runs remain fully readable and correctly attributed to the old version of the code.
- Read-only web UI with run overview, per-record tracing, and field statistics.
- Installable and runnable via both `pip install squeegee` and `uvx squeegee`.
- Works with no third-party runtime dependencies for the core; the UI is an optional install extra.

### Should have

- Dropping a record from the pipeline by returning `None`, recorded as a drop rather than an error.
- An opt-in `--continue-on-error` that records the failure and carries on with the remaining records, for when the developer wants the full picture of what is broken in one pass.
- Sampling and limiting flags so a developer can trial a pipeline against the first N records.
- Comparison of two runs of the same script.

### Out of scope for v1

- Data formats other than CSV and JSON.
- Branching pipelines, fan-out, or joins between sources.
- Aggregate stages that see the whole dataset at once.
- Remote or shared storage; the database is a local file.
- Authentication in the UI. It binds to localhost only.

## Success criteria

- A developer can convert an existing throwaway cleaning script to Squeegee stages in under ten minutes.
- Given a wrong output record, the developer can identify the stage responsible in under one minute using the UI.
- A first run on a ten thousand record CSV completes in a few seconds on a laptop, including persistence.
