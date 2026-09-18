# HTTP API Reference

The read-only JSON API behind the UI, served by `squeegee ui` from `src/squeegee/ui/server.py`. This file is the contract between the server and the React client, written by hand because a stdlib server generates no OpenAPI document. See [decisions/0002-react-ui-on-a-stdlib-server.md](decisions/0002-react-ui-on-a-stdlib-server.md).

A test asserts that every route registered in `server.py` appears in this file. Adding an endpoint without documenting it fails CI.

## Conventions

- Base URL `http://127.0.0.1:{port}`. All endpoints are `GET`. There is no endpoint that writes.
- All responses are `application/json`, UTF-8, with `Content-Length` set.
- Timestamps are ISO 8601 in UTC with a `Z` suffix.
- Durations are integer microseconds, named `*_us`.
- Record values are returned as parsed JSON, not as the strings they are stored as. A value that could not be serialized during the run comes back as `{"__squeegee_unserializable__": "<repr>"}`.
- Absent optional fields are `null` rather than omitted, so the client has one shape to handle.

## Errors

Every error uses the same envelope, at every status code:

```json
{ "error": { "code": "invalid_parameter", "message": "limit must be between 1 and 500", "parameter": "limit" } }
```

| Status | `code` | When |
| --- | --- | --- |
| 400 | `invalid_parameter` | A query parameter is missing, unparseable, or out of bounds. `parameter` names it. |
| 404 | `not_found` | An unknown path under `/api`, or a run, stage position, record index, or field that does not exist. |
| 500 | `internal_error` | An unhandled exception. The message is the exception string; the traceback goes to the server's stderr, never to the client. |

Unknown paths that are not under `/api` are not errors. They serve `index.html` so that client-side routing survives a refresh.

## Pagination

List endpoints are cursor-paginated on the primary key, ascending unless stated.

- `limit`: integer, 1 to 500, default 50.
- `cursor`: opaque string from the previous response's `next_cursor`. Absent means start at the beginning.

Every list response has the same envelope:

```json
{ "items": [ ... ], "next_cursor": "1042", "has_more": true }
```

`next_cursor` is `null` when `has_more` is `false`.

## Endpoints

### `GET /api/meta`

Server and database identity, for the UI header.

```json
{
  "squeegee_version": "0.1.0",
  "database_path": "/home/dev/work/.squeegee/squeegee.db",
  "run_count": 42
}
```

### `GET /api/runs`

Paginated run list, newest first. Optional `script` parameter filters by substring of `script_path`.

```json
{
  "items": [
    {
      "run_id": 42,
      "script_path": "clean_orders.py",
      "input_path": "orders.csv",
      "output_path": "clean.csv",
      "started_at": "2026-09-18T14:02:11Z",
      "ended_at": "2026-09-18T14:02:14Z",
      "duration_us": 2841003,
      "status": "finished",
      "stage_count": 5,
      "records_in": 10000,
      "records_out": 9863,
      "records_dropped": 131,
      "records_errored": 6
    }
  ],
  "next_cursor": null,
  "has_more": false
}
```

`status` is one of `started`, `finished`, `failed`, `aborted`, derived from the `run_status` view.

### `GET /api/runs/{run_id}`

One run's metadata and totals. Same fields as a list item, plus provenance:

```json
{
  "run_id": 42,
  "script_path": "/home/dev/work/clean_orders.py",
  "script_sha256": "9f2c...",
  "input_path": "orders.csv",
  "output_path": "clean.csv",
  "started_at": "2026-09-18T14:02:11Z",
  "ended_at": "2026-09-18T14:02:14Z",
  "duration_us": 2841003,
  "status": "failed",
  "squeegee_version": "0.1.0",
  "python_version": "3.12.4",
  "options": { "limit": null, "sample": null, "continue_on_error": false, "fail_fast": true },
  "records_in": 10000,
  "records_out": 0,
  "records_dropped": 131,
  "records_errored": 1,
  "failure": {
    "stage_position": 2,
    "stage_name": "parse_amount",
    "record_index": 4471,
    "error_type": "ValueError",
    "error_message": "could not convert string to float: 'n/a'"
  }
}
```

`failure` is `null` unless `status` is `failed`. Because fail-fast is the default, this object is what the UI leads with on a failed run.

### `GET /api/runs/{run_id}/stages`

Every stage of the run in declaration order, with counts and timings. Not paginated; a pipeline is a handful of stages.

```json
{
  "items": [
    {
      "position": 0,
      "stage_version_id": 7,
      "name": "parse_amount",
      "description": "Convert the amount column from a currency string to cents.",
      "records_in": 10000,
      "records_ok": 9994,
      "records_dropped": 0,
      "records_errored": 6,
      "duration_us_total": 412003,
      "duration_us_median": 38,
      "duration_us_p95": 71
    }
  ]
}
```

### `GET /api/runs/{run_id}/stages/{position}`

One stage, including the source text the UI renders with syntax highlighting.

```json
{
  "position": 0,
  "stage_version_id": 7,
  "name": "parse_amount",
  "description": "Convert the amount column from a currency string to cents.",
  "input_type": "dict[str, Any]",
  "output_type": "dict[str, Any] | None",
  "source_text": "@stage\ndef parse_amount(record):\n    ...\n",
  "source_sha256": "4b81...",
  "source_language": "python",
  "first_seen_at": "2026-09-14T09:31:02Z",
  "also_used_by_runs": [39, 40, 41],
  "counts": { "records_in": 10000, "records_ok": 9994, "records_dropped": 0, "records_errored": 6 }
}
```

`input_type` and `output_type` are `null` when the user did not annotate. `source_text` is the exact dedented source as it ran, never reformatted by the server; highlighting is the client's job. `also_used_by_runs` lists other runs that used this identical stage version, which is what makes cross-run comparison discoverable.

### `GET /api/runs/{run_id}/stages/{position}/records`

Paginated record events for one stage.

| Parameter | Type | Notes |
| --- | --- | --- |
| `status` | `ok`, `dropped`, `error` | Optional. Absent means all. |
| `q` | string | Optional. Case-insensitive substring match against the stored input and output JSON. |
| `limit`, `cursor` | | Standard pagination. |

```json
{
  "items": [
    {
      "record_index": 4471,
      "status": "error",
      "input": { "id": "4471", "amount": "n/a" },
      "output": null,
      "error_type": "ValueError",
      "error_message": "could not convert string to float: 'n/a'",
      "duration_us": 41
    }
  ],
  "next_cursor": "4600",
  "has_more": true
}
```

### `GET /api/runs/{run_id}/records/{record_index}`

The full trace of one record through the pipeline. This is the debugging screen's single query.

```json
{
  "record_index": 4471,
  "source": { "id": "4471", "amount": "n/a" },
  "final_status": "error",
  "events": [
    {
      "position": 0,
      "stage_name": "normalize_headers",
      "status": "ok",
      "input": { "ID": "4471", "Amount": "n/a" },
      "output": { "id": "4471", "amount": "n/a" },
      "changed_fields": ["id", "amount"],
      "duration_us": 22
    },
    {
      "position": 1,
      "stage_name": "parse_amount",
      "status": "error",
      "input": { "id": "4471", "amount": "n/a" },
      "output": null,
      "changed_fields": [],
      "error_type": "ValueError",
      "error_message": "could not convert string to float: 'n/a'",
      "duration_us": 41
    }
  ]
}
```

`changed_fields` is computed server side by comparing each event's input and output at the top level, so the client highlights rather than diffs. The list ends at the stage where the record was dropped or errored; it does not contain placeholder entries for stages that never ran.

Two optional parameters support the previous and next controls: `status` restricts stepping to records with a given final status, and the response includes `previous_record_index` and `next_record_index` under that restriction, either of which may be `null`.

### `GET /api/runs/{run_id}/stages/{position}/fields`

Per-field statistics over the stage's `ok` outputs, computed with SQLite aggregates over `json_extract`.

```json
{
  "records_considered": 9994,
  "items": [
    {
      "field": "amount_cents",
      "inferred_type": "number",
      "non_null_count": 9990,
      "null_count": 4,
      "distinct_count": 4123,
      "min": 0,
      "max": 918400,
      "mean": 4213.77,
      "median": 2999,
      "sum": 42091542
    },
    {
      "field": "status",
      "inferred_type": "string",
      "non_null_count": 9994,
      "null_count": 0,
      "distinct_count": 4,
      "min": null, "max": null, "mean": null, "median": null, "sum": null
    }
  ]
}
```

Numeric statistics are `null` for non-numeric fields. `inferred_type` is one of `number`, `string`, `boolean`, `object`, `array`, `mixed`, decided by what the stored values actually are, not by any annotation.

### `GET /api/runs/{run_id}/stages/{position}/fields/{field}`

Distribution detail for one field, plus the same field before the stage, which is what makes a transformation verifiable at a glance.

| Parameter | Type | Notes |
| --- | --- | --- |
| `bins` | integer, 5 to 50, default 20 | Histogram bins, numeric fields only. |
| `top` | integer, 1 to 100, default 20 | Number of top values for non-numeric fields. |

```json
{
  "field": "amount_cents",
  "inferred_type": "number",
  "after": {
    "stats": { "non_null_count": 9990, "null_count": 4, "distinct_count": 4123, "min": 0, "max": 918400, "mean": 4213.77, "median": 2999, "sum": 42091542 },
    "histogram": [ { "lower": 0, "upper": 45920, "count": 8814 } ],
    "top_values": null
  },
  "before": {
    "stats": { "non_null_count": 10000, "null_count": 0, "distinct_count": 4131, "min": null, "max": null, "mean": null, "median": null, "sum": null },
    "histogram": null,
    "top_values": [ { "value": "$29.99", "count": 311 } ]
  }
}
```

`before` is `null` for the first stage, whose input is the source record, and for a field that did not exist in the input. `histogram` is populated for numeric fields and `top_values` for everything else; exactly one of the two is non-null in each block.
