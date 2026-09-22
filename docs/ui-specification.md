# UI Specification

## Purpose and constraints

The UI is a local, read-only window onto the SQLite database. It answers three questions: what happened in this run, what happened to this record, and do the numbers look right.

- Launched with `squeegee ui`, bound to `127.0.0.1` only, no authentication, no external network calls.
- Read-only. There are no buttons that write, re-run, edit, or delete. The server opens SQLite in read-only mode so this is structural, not just a UI choice.
- Stack: a React single page application, built ahead of time, served by Python's standard library `http.server` alongside a small read-only JSON API. No FastAPI, no Uvicorn, no install extra; the package has no runtime dependencies at all.
- Users never build anything. The wheel ships the built assets. Node is a contributor requirement only.
- Components are hand-written with plain CSS. No component library, no CSS framework.
- Icons come from Lucide, imported individually from `lucide-react` so the bundle stays tree-shaken. Icons are decorative support for a text label, never the only affordance.
- Designed for a laptop screen at 1280px and up. Responsive down to tablet width; phone support is not a goal.

## The chosen layout

Option 2, Split View, from [ui-wireframes/](ui-wireframes/). The runs list is its own screen; everything else lives in one three pane view of a run, because the product requirement is finding the stage responsible for a wrong record in under a minute, and that is hard when stage, records, source, and trace are on four different pages.

State that a developer would want to share or return to lives in the query string: `?stage=2&record=8&status=error&step=error&q=n%2Fa&field=amount_cents`. A refresh restores the same view.

`status` and `step` are deliberately separate. `status` filters the record table on what the selected stage did to each record, while `step` decides which records the trace's previous and next controls walk through, and that filters on where a record finally ended up. Sharing one parameter between them means the next control can land on a record that is not in the table.

Every parameter is validated when it is read. An unparseable stage falls back to the first one, an empty or non-numeric record is treated as no record rather than as record zero, and a status that is not one of the three known values is ignored rather than forwarded to the API.

## Screens

### 1. Runs list

The landing page. A table of every run, newest first: run id, script name, input file, started time, duration, status, and the counts in / out / dropped / errored. Clicking a row opens the run overview. A filter box narrows by script name.

### 2. Run overview

The most important screen. Shows the pipeline as a vertical sequence of stages, in declaration order, each one a card carrying:

- Stage name and description.
- Records in, records out, records dropped, records errored.
- Median and total stage duration.
- A drop indicator sized to the proportion of records the stage removed, so a stage that silently eats most of the input is visible at a glance.

Above the stages sits a summary strip with the run metadata and the overall funnel from input count to output count. Clicking a stage card opens the stage detail. Clicking an error count opens the stage detail already filtered to errors.

### 3. Stage detail

For one stage in one run: a paginated table of the records that passed through it, and below the table the selected record's input and output for that stage side by side, input on the left and output on the right. Each row of the table shows the record index, status, and duration; the row previews of the stored JSON were dropped because a truncated one-line blob answers no question the panel below does not answer better. Filters: status (ok, dropped, error) and a text search across the JSON. Selecting a row fills the input and output panel and opens the record trace.

The stage's source code, rendered per the code display rules below, and its input and output type annotations where the user wrote any, are opened on demand from the code icon on the stage's row in the stages list, rather than holding permanent vertical space under the table.

#### Code display

The source of a stage is first-class content on this screen, not a footnote. It is the thing the developer reads to work out why a value came out wrong, so it gets the same care as the data.

- Monospace throughout, from a stack of `ui-monospace`, `SFMono-Regular`, `Menlo`, `Consolas`, `monospace`, at a size that stays readable next to the data tables.
- Python syntax highlighting, using `prism-react-renderer` with the Python grammar only. No other languages are registered, so the grammar cost stays small. The theme is a local object written against the UI's CSS custom properties rather than an imported theme package, so the code block follows the system theme through the same variables as everything else and never ends up light on a dark page.
- The highlight theme is defined in terms of the same CSS custom properties as the rest of the UI, so light and dark follow the system preference without a second theme package.
- The source is exactly what ran, byte for byte, as stored in `stage_versions.source_text`. It is never reformatted, re-indented, or prettified by the client.
- Line numbers on the left, starting at 1 relative to the stage's own source rather than the original file.
- Long lines scroll horizontally. They do not wrap, because wrapped Python misleads about indentation.
- A copy button yields the raw source with no line numbers.
- Where a stage raised, the exception type and message take the place of the output, and a view source control next to them opens that stage's source, so the code is one click from the failure.

The same component renders the stage source in the record trace panels, collapsed by default there so the data stays the focus.

### 4. Record trace

The debugging screen. For one record: its source value at the top, then one panel per stage showing input, output, status, and duration. Changed fields are highlighted against the previous stage's value, so the developer can see which stage introduced the wrong value without reading two JSON blobs side by side. Where the record was dropped or errored, the panel shows the reason and the trace ends there. Previous and next controls step through neighbouring records with the same status, which makes scanning a run's errors quick.

### 5. Field analytics

For one stage in one run, a table of every field present in the outputs: field name, inferred type, non-null count, null count, distinct count, and, for numeric fields, min, max, mean, median, and sum. Selecting a field shows its distribution: a histogram for numeric fields, top values for categorical ones. A toggle compares the same field before and after the stage, which is the fastest way to confirm a transformation did what was intended.

All statistics are computed with SQLite aggregates over `json_extract` on the stored JSON, server side. No pandas, no in-memory dataframe, and no shipping a whole run to the browser to be reduced there.

### 6. Run comparison (should-have, may land after v1)

Two runs of the same script side by side, with per-stage count deltas, so the developer can see what changing a stage did to the shape of the output.

## API

All endpoints are read-only `GET`, return JSON, and are versioned under `/api`.

| Endpoint | Returns |
| --- | --- |
| `GET /api/runs` | Paginated run list with status and summary counts. |
| `GET /api/runs/{run_id}` | Run metadata, script hash, options, overall counts. |
| `GET /api/runs/{run_id}/stages` | Ordered stages with per-status counts and duration percentiles. |
| `GET /api/runs/{run_id}/stages/{position}` | One stage plus its source text and annotations, which may be null. |
| `GET /api/runs/{run_id}/stages/{position}/records` | Paginated record events for that stage, filterable by status and free text. |
| `GET /api/runs/{run_id}/records/{record_index}` | Full trace of one record across every stage. |
| `GET /api/runs/{run_id}/stages/{position}/fields` | Per-field statistics for the stage's outputs. |
| `GET /api/runs/{run_id}/stages/{position}/fields/{field}` | Distribution detail for one field. |

Pagination is cursor-based on the primary key. Every list endpoint caps its page size so a large run cannot be turned into a multi-megabyte response by a query parameter.

Routing, pagination, parameter parsing, and error responses are hand-written, since no framework validates them. Unknown paths under `/api` return 404 as JSON; any other path falls through to the static asset handler, which serves `index.html` so client-side routing works on a page refresh. Malformed parameters return 400 with a message naming the parameter.

## Hand-written server checklist

Nothing here is exotic; all of it is what a framework would have handled. Each item is a required test case.

- **MIME types are set explicitly at startup.** `mimetypes` consults the Windows registry, where `.js` is often mapped to `text/plain`, which makes the browser refuse the module scripts. Call `mimetypes.add_type` for `.js`, `.mjs`, `.css`, `.json`, `.svg`, and `.woff2` before serving anything.
- **Static serving reuses `SimpleHTTPRequestHandler.translate_path`.** It already normalizes away `..` and absolute paths. Hand-rolled path joining is where directory traversal gets introduced.
- **Unknown non-API paths serve `index.html`** with a 200, so a refresh on a client-side route works. Unknown paths under `/api` return 404 as JSON.
- **`ThreadingHTTPServer` with `daemon_threads = True`**, so Ctrl-C exits immediately instead of waiting on open connections.
- **One SQLite connection per thread**, held in thread-local storage, each opened read-only through a `file:...?mode=ro` URI. `sqlite3` connection objects are not shared across threads.
- **Bind `127.0.0.1` explicitly**, never `0.0.0.0`. The UI has no authentication because it is unreachable from the network, and that has to stay true.
- **A busy port exits with a clear message** naming the port and suggesting `--port`, rather than an `OSError` traceback.
- **Query parameters are parsed and bounded in one place.** `limit` is an integer clamped to a maximum, `cursor` is an integer or absent, `status` is one of the three known values. A bad parameter returns 400 with a message naming it, never a 500.
- **Every response sets `Content-Type` and `Content-Length`**, and errors are the same JSON envelope as successes so the client has one parsing path.
- **No gzip.** Over loopback, for a bundle this size, it is not worth the code.

## Visual direction

Utilitarian and dense, closer to a debugger than a dashboard. Monospace for data values, a normal UI font for chrome. A restrained palette with one accent colour; status is carried by consistent colours for ok, dropped, and error, used identically on every screen, and never by colour alone. Dark and light both supported through CSS custom properties, following the system preference. JSON values are rendered in a collapsible tree, not as a wall of text.

Wireframes for each screen go in [ui-wireframes/](ui-wireframes/) and are the next deliverable after these specifications are approved.
