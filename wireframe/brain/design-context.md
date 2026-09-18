# Design Context — Squeegee

Generated: 2026-09-18

## App Overview

Squeegee is a Python package for cleaning and transforming small data during ordinary development work. A developer writes a script where each transformation is one function decorated with `@stage`, runs it through the Squeegee CLI, and every intermediate input and output is recorded to an append-only local SQLite database. `squeegee ui` opens a local, read-only web UI over that database.

There is no existing client-facing code yet; this context is derived from the specifications in `docs/`, not from an implementation or screenshots. Update it once the UI exists.

## Target Platform

Desktop / Web. A local developer tool opened at `127.0.0.1` on a laptop, 1280px and up. Responsive down to tablet width; phones are not a goal.

## Layout Patterns

- Dense, utilitarian, closer to a debugger than a dashboard.
- Content is a mix of tables (records), cards (stages), code (stage source), and key-value metadata blocks (run provenance).
- A persistent header carries the database path, the Squeegee version, and the current run.

## Navigation

- Five screens: runs list, run overview, stage detail, record trace, field analytics.
- Navigation is hierarchical and drill-down: run → stage → record. Breadcrumbs carry the way back.
- Everything is read-only. There are no create, edit, or delete affordances anywhere.

## Page Types

### Runs list
- Structure: full-width table, newest first.
- Key elements: run id, script, input file, started time, duration, status, and counts in / out / dropped / errored.

### Run overview
- Structure: metadata strip on top, then the pipeline as an ordered sequence of stage cards.
- Key elements: per-stage counts, drop proportion, timings, and, for a failed run, the failure banner naming the stage, the record, and the exception.

### Stage detail
- Structure: stage source code plus a paginated record table.
- Key elements: syntax-highlighted Python with line numbers, type annotations where present, status filter, free-text search.

### Record trace
- Structure: the source record, then one panel per stage, in order.
- Key elements: input, output, changed-field highlighting, duration, and the reason a record was dropped or errored.

### Field analytics
- Structure: a field table, then a distribution panel for the selected field.
- Key elements: counts, nulls, distinct, min, max, mean, median, sum, histogram or top values, and a before/after comparison across the stage.

## Interaction Patterns

- Filtering by status, free-text search over stored JSON, cursor pagination.
- Collapsible JSON trees rather than walls of text.
- Previous and next controls that step through records sharing a status.
- No forms that submit, no modals that mutate.

## Content Hierarchy

- Data values are monospace; chrome is a normal UI font.
- Status is one of ok, dropped, error, shown consistently and never by colour alone.
- Stage source code is first-class content, not a footnote.

## UX Conventions

- Fail fast: a failed run leads with its failure, rather than burying it in a count.
- Counts are always four numbers in the same order: in, ok, dropped, errored.
- Nothing in the UI implies that a value can be changed.
