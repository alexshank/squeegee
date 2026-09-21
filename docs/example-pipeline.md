# The Example Pipeline

A small, real pipeline lives in [`examples/`](../examples). It exists to be read, to be run, and to be the fixture that validation leans on. Every number printed below is asserted in `tests/test_examples.py`, so if the tool's behaviour drifts, the tests fail rather than this document quietly going stale.

## The files

| File | What it is |
| --- | --- |
| [`examples/clean_orders.py`](../examples/clean_orders.py) | Five stages, none of them annotated, because a user script never has to be |
| [`examples/orders.csv`](../examples/orders.csv) | Ten rows of plausible mess: mixed-case headers, currency strings, internal test accounts, a malformed email, a duplicate order |
| [`examples/orders_with_a_bad_row.csv`](../examples/orders_with_a_bad_row.csv) | The same ten rows, except order 1008's amount is `n/a`, which makes `parse_amount` raise |

## The stages

| Position | Stage | What it does |
| --- | --- | --- |
| 0 | `normalize_headers` | Lowercases column names and turns spaces into underscores, so `Order ID` becomes `order_id` |
| 1 | `drop_internal_test_orders` | Returns `None` for `@internal.test` addresses, dropping them |
| 2 | `parse_amount` | Turns `"$1,299.00"` into `129900`. Raises `ValueError` on anything that is not a number |
| 3 | `validate_email` | Drops records whose email cannot be an email |
| 4 | `dedupe_by_id` | Keeps the first record for each order id and drops the rest |

Two things in there are worth noticing. The stage at position 1 is registered as `drop_internal_test_orders` through `@stage(name=...)` while the function is called `drop_test_rows`, which is how a stage gets a name that reads well in the UI. And `dedupe_by_id` holds state between records, which Squeegee allows but which makes the result depend on the order records arrive in.

## The happy path

```
squeegee run examples/clean_orders.py --input examples/orders.csv --output /tmp/clean.csv --db /tmp/squeegee.db
```

```
run 1 finished: 10 in, 6 out, 4 dropped, 0 errored, 0.05s
recorded in /tmp/squeegee.db
```

Exit code 0. Four records are dropped, and each for a different reason: two internal test accounts at stage 1, one malformed email at stage 3, one duplicate order at stage 4. `/tmp/clean.csv` holds:

```
order_id,email,placed_on,amount_cents
1001,ada@example.com,2026-09-01,2999
1003,grace@example.com,2026-09-02,129900
1005,linus@example.com,2026-09-03,400
1006,margaret@example.com,2026-09-04,13000
1008,katherine@example.com,2026-09-05,7820
1009,barbara@example.com,2026-09-05,999
```

## The failing path

```
squeegee run examples/clean_orders.py --input examples/orders_with_a_bad_row.csv --output /tmp/clean.csv --db /tmp/squeegee.db
```

```
run 2 failed at stage 2 (parse_amount), record 8: ValueError: could not convert string to float: 'n/a'
run 2 failed: 9 in, 4 reached the last stage, 4 dropped, 1 errored, 0.01s
recorded in /tmp/squeegee.db
```

Exit code 1, the first line on stderr. Fail fast is the default, so the run stops at record 8 rather than working through the remaining row. Nine records were read rather than ten, because the tenth was never reached. No output file is written at all: half a cleaned CSV is worse than none. Everything processed before the failure is still in the database, which is the whole point.

## Continuing past the failure

```
squeegee run examples/clean_orders.py --input examples/orders_with_a_bad_row.csv --output /tmp/clean.csv --db /tmp/squeegee.db --continue-on-error
```

```
run 3 finished: 10 in, 5 out, 4 dropped, 1 errored, 0.01s
recorded in /tmp/squeegee.db
```

Exit code 0. The error is recorded against record 8 and the run carries on, so the output holds the five records that survived everything: 1001, 1003, 1005, 1006, and 1009. Order 1008 is missing, because it errored.

## Reading the recorded runs

Until the web UI exists, two subcommands read the same database:

```
squeegee runs --db /tmp/squeegee.db
```

```
    3  finished  2026-09-20T17:22:44.132263Z  clean_orders.py  10 in, 5 out, 4 dropped, 1 errored
    2  failed    2026-09-20T17:22:44.039048Z  clean_orders.py  9 in, 4 out, 4 dropped, 1 errored
    1  finished  2026-09-20T17:22:38.636227Z  clean_orders.py  10 in, 6 out, 4 dropped, 0 errored
```

```
squeegee show 2 --db /tmp/squeegee.db
```

```
run 2  failed  /path/to/examples/clean_orders.py
  input  examples/orders_with_a_bad_row.csv
  output /tmp/clean.csv
  9 in, 4 out, 4 dropped, 1 errored
   0  normalize_headers              9 in       9 ok     0 dropped    0 errored
   1  drop_internal_test_orders      9 in       7 ok     2 dropped    0 errored
   2  parse_amount                   7 in       6 ok     0 dropped    1 errored
   3  validate_email                 6 in       5 ok     1 dropped    0 errored
   4  dedupe_by_id                   5 in       4 ok     1 dropped    0 errored
  failed in stage 2 (parse_amount) on record 8: ValueError: could not convert string to float: 'n/a'
```

Read the stage table as a funnel: nine records entered, two were internal test accounts, one had an unparseable amount, one had a malformed email, and one was a duplicate.

## Using it for validation

The three paths above are asserted end to end in `tests/test_examples.py`, which runs the real script over the real CSVs through the real CLI:

```
uv run pytest tests/test_examples.py
```

This is the fixture to reach for when building the rest of the tool. A run of the example produces a database holding every status the UI has to render — `ok`, `dropped`, and `error` — across five stages and two runs of the same pipeline, one of which failed. Point the query layer, the HTTP server, and the UI screens at a database built this way rather than inventing fixtures for each.

To produce one:

```
rm -rf /tmp/squeegee-demo && mkdir /tmp/squeegee-demo
squeegee run examples/clean_orders.py --input examples/orders.csv --output /tmp/squeegee-demo/clean.csv --db /tmp/squeegee-demo/squeegee.db
squeegee run examples/clean_orders.py --input examples/orders_with_a_bad_row.csv --db /tmp/squeegee-demo/squeegee.db
squeegee run examples/clean_orders.py --input examples/orders_with_a_bad_row.csv --db /tmp/squeegee-demo/squeegee.db --continue-on-error
```

Three runs of one script, with two different inputs and one edited option set, in a single append-only database.
