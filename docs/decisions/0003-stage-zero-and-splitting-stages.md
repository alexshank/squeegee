# 0003. The reader is stage zero, and splitting is a stage kind

- Status: accepted (stage zero); proposed (splitting stages)
- Date: 2026-10-05

## Context

A run used to start with records already in hand. How the input became records (a CSV read row by row, a journal split on dates) was invisible, even though it is the first place a value can go wrong. Later, inputs will come from more than files: parquet, SQLite, Postgres, a directory of files. And some pipelines need a stage that turns one record into many, which is the same shape as reading an input: one invocation, many records out.

## Decision

The reader is recorded as **stage zero** of every run. It is an ordinary `run_stages` row whose `stage_versions.kind` is `source`, carrying the reader's own source text. Each record gets a stage zero event whose input is the raw slice it was read from (a CSV line, a JSON line, a text block) and whose output is the parsed record. The script's stages follow at positions 1 and up.

A reader is any callable `Path -> Iterator[(raw, record)]`. It is chosen by a script's `register_reader`, then by extension, then by sniffing the content (JSON, then CSV), falling back to plain text. `stage_versions.input_format` tells the UI how to highlight the raw slices; when it is empty the UI infers (JSON if the value parses, plain text otherwise).

## Splitting stages (next)

A splitting stage is a third `kind`, `split`: a function from one record to an iterable of records.

- The parent's event at the split stage has status `split` and its trace ends there.
- Each child is a new `records` row with `parent_record_id` and `origin_position`, and its trace starts with an event at the split stage whose input is the parent and whose output is the child.
- Stage zero is then the special case whose parent is the input itself rather than a record.

Non-file sources (a database, a directory) fit the same contract: the "path" becomes a source specification, and the raw slice becomes whatever unit the source yields (a row, a file).

## Consequences

- Positions shift by one: a script's first stage is at position 1.
- The schema gained `stage_versions.kind` and `stage_versions.input_format`, so `PRAGMA user_version` is now checked and a database from another schema is refused rather than migrated, consistent with the append-only rule.
