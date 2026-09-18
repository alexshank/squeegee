# Squeegee Specifications

This directory holds the specification documents for Squeegee. Implementation agents should read these before writing any code. No production code exists yet by design: the specs come first, then wireframes, then tooling, then implementation.

| Document | Purpose |
| --- | --- |
| [product-requirements.md](product-requirements.md) | What Squeegee is for, who uses it, what is in and out of scope. |
| [technical-specification.md](technical-specification.md) | Package layout, public API, decorator semantics, CLI, execution model. |
| [data-model.md](data-model.md) | ERD, SQLite schema, append-only rules, versioning of stages and runs. |
| [ui-specification.md](ui-specification.md) | Local read-only web UI: screens, endpoints, analytics. |
| [engineering-standards.md](engineering-standards.md) | Linting, formatting, typing, testing, coverage, pre-commit, CI. |
| [ui-wireframes/](ui-wireframes/) | Wireframes for the UI screens. Generated in the next step. |

## Status

- [x] Repository created
- [ ] Specifications reviewed and approved
- [ ] UI wireframes generated and committed
- [ ] Tooling scaffolded (uv, ruff, mypy, pytest, pre-commit, CI)
- [ ] Implementation

## Decisions already made

These are settled. Implementation agents should not revisit them without asking.

1. Stage functions process **one record at a time**, not whole datasets. This is what makes per-record tracing possible in the UI.
2. Pipeline order is **declaration order** in the user's script. No DAG, no explicit dependency graph.
3. Supported data formats are **CSV and JSON only**. The reader/writer layer is pluggable so other formats can be added later.
4. The core package has **no third-party runtime dependencies**. The web UI is an optional extra.
5. The storage layer is **append-only SQLite**. Nothing is ever updated or deleted.
6. The UI is **read-only**. It explores and reviews past runs; it never triggers or edits a pipeline.
7. Runs **fail fast**. The first stage exception aborts the run, after recording it. `--continue-on-error` is the opt-out.
8. Strict typing is a rule for **this repository only**. User scripts need no annotations, and Squeegee never fails a run over one.
