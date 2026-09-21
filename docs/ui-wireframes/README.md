# UI Wireframes

Black and white wireframes for the screens defined in [../ui-specification.md](../ui-specification.md). Structure only: layout, hierarchy, and controls. No colour, no typography decisions.

## Pipeline run explorer

[pipeline-run-explorer/index.html](pipeline-run-explorer/index.html) — open in a browser. Five approaches to the same data, each interactive, with numbered UX notes under each one, plus a summary tab.

| Option | Approach | Best at |
| --- | --- | --- |
| 1. Drill Down | Hierarchical pages: run, then stage, then record | Reading a run top to bottom the way you read a log |
| 2. Split View | Stages, records, and one record's trace on a single screen | Debugging: changing stage or record without losing context |
| 3. Pipeline Funnel | The funnel is the navigation; selecting a stage swaps code and statistics | Reviewing whether a transformation did what was intended |
| 4. Command Palette | One keyboard-driven input addresses everything | Jumping straight to a known record index |
| 5. Record Matrix | The run as a grid: records down, stages across | Seeing failure patterns across a whole run at once |

**Chosen: Option 2, Split View**, and now implemented in `frontend/`. The product requirement is that a developer can identify the stage responsible for a wrong record in under a minute, and the split view is the only option where the stage list, the records, the stage source, and the trace are all reachable without navigating. Option 3's funnel is worth folding in as the run overview that leads into it, and Option 1 is the fallback at narrow widths.

Every option shows the same scenario: run 42 of `clean_orders.py`, which failed fast at stage 2, `parse_amount`, on record 4471, with 4,470 records already processed and still reviewable.

Wireframes for field analytics as a standalone screen are not drawn yet; Option 3 covers the layout in part.

## Design context

`../../wireframe/brain/` holds the design context and taste notes used to generate these. They are inputs to the wireframe tooling, not specifications.
