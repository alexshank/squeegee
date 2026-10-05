# The Example Pipeline

A small, real pipeline lives in [`examples/`](../examples). It exists to be read, to be run, and to be the fixture that validation leans on. Every number printed below is asserted in `tests/test_examples.py`, so if the tool's behaviour drifts, the tests fail rather than this document quietly going stale.

## The files

| File | What it is |
| --- | --- |
| [`examples/clean_orders.py`](../examples/clean_orders.py) | Eight stages, none of them annotated, because a user script never has to be |
| [`examples/orders.csv`](../examples/orders.csv) | Ten rows of plausible mess: mixed-case headers, currency strings, internal test accounts, a malformed email, a duplicate order, and line items packed into one column |
| [`examples/orders_with_a_bad_row.csv`](../examples/orders_with_a_bad_row.csv) | The same ten rows, except order 1008's amount is `n/a`, which makes `parse_amount` raise |

## The stages

| Position | Stage | What it does |
| --- | --- | --- |
| 0 | `read_csv` | Stage zero: the reader, one record per CSV row, with the raw line as its input |
| 1 | `normalize_headers` | Lowercases column names and turns spaces into underscores, so `Order ID` becomes `order_id` |
| 2 | `drop_internal_test_orders` | Returns `None` for `@internal.test` addresses, dropping them |
| 3 | `parse_amount` | Turns `"$1,299.00"` into `129900`. Raises `ValueError` on anything that is not a number |
| 4 | `validate_email` | Drops records whose email cannot be an email |
| 5 | `dedupe_by_id` | Keeps the first record for each order id and drops the rest |
| 6 | `parse_line_items` | Turns `"widget x2; gadget x1"` into a nested list of `{"sku", "quantity"}` objects |
| 7 | `nest_the_customer` | Moves the email into a nested `customer` object beside its domain |
| 8 | `to_csv_text` | Returns CSV text, a header and one row, instead of a dictionary; nested fields become JSON inside it |

Two things in there are worth noticing. The stage at position 2 is registered as `drop_internal_test_orders` through `@stage(name=...)` while the function is called `drop_test_rows`, which is how a stage gets a name that reads well in the UI. `to_csv_text` shows that a stage may return text: the UI highlights it as CSV, and the CSV writer reads it back into rows. And `dedupe_by_id` holds state between records, which Squeegee allows but which makes the result depend on the order records arrive in.

## The happy path

```
squeegee run examples/clean_orders.py --input examples/orders.csv --output /tmp/clean.csv --db /tmp/squeegee.db
```

```
run 1 finished: 10 in, 6 out, 4 dropped, 0 errored, 0.05s
recorded in /tmp/squeegee.db
```

Exit code 0. Four records are dropped, and each for a different reason: two internal test accounts at stage 2, one malformed email at stage 4, one duplicate order at stage 5. `/tmp/clean.csv` holds:

```
order_id,placed_on,items,amount_cents,customer
1001,2026-09-01,"[{""sku"": ""widget"", ""quantity"": 2}, {""sku"": ""gadget"", ""quantity"": 1}]",2999,"{""email"": ""ada@example.com"", ""domain"": ""example.com""}"
1003,2026-09-02,"[{""sku"": ""laptop"", ""quantity"": 1}]",129900,"{""email"": ""grace@example.com"", ""domain"": ""example.com""}"
...
```

## The failing path

```
squeegee run examples/clean_orders.py --input examples/orders_with_a_bad_row.csv --output /tmp/clean.csv --db /tmp/squeegee.db
```

```
run 2 failed at stage 3 (parse_amount), record 8: ValueError: could not convert string to float: 'n/a'
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

## A second example: a text file

[`examples/words_2022.py`](../examples/words_2022.py) runs over [`examples/words-2022.txt`](../examples/words-2022.txt), a journal of quotes somebody kept by hand through 2022. It is here because it is the opposite of `orders.csv`: no header row, no delimiter, and entries that run across blank lines.

Blank lines separate entries in most of the file, but not in all of it — three entries contain blank lines of their own, and one holds two quotes under a single date. A stage takes one record and returns one record, so it cannot join a continuation line onto the record before it. The split therefore has to happen in the reader, and the script says so itself:

```python
register_reader(".txt", blocks_starting_with(r"\d{1,2}/\d{1,2}"))
```

A new record starts at every line that opens with a date; everything after it, blank lines included, belongs to that record. The text before the first date — the file's title — is yielded as a record too, rather than dropped silently, and the first stage drops it where the run can show it happening.

Everything else is an ordinary stage:

| Position | Stage | What it does |
| --- | --- | --- |
| 0 | `drop_the_title` | Returns `None` for the one block that does not begin with a date |
| 1 | `split_the_date_from_the_body` | Separates the leading date from the entry, collapsing the whitespace an entry spanning blank lines carries |
| 2 | `parse_the_date` | `01/01`, `11/17/22` and `11/21/2022` all become an ISO date |
| 3 | `collect_the_quotes` | Pulls out each quoted passage; an entry written without quote marks keeps its whole body as one passage |
| 4 | `attribute_each_quote` | Tidies the attribution that follows each closing quote |
| 5 | `classify_each_quote` | Asks [Jev](https://docs.typesafe.ai) which kind of work each quote came from: film, TV, music, book, anime, a real person, or other |

The last stage calls TypeSafe's hosted classifier once per quote, so the run needs `TYPESAFE_API_KEY` in the environment. Every entry in the file is a quote, so classifying "quote or word" would say nothing; the medium is the split worth having. The answer's `confidence` is kept next to the choice, so a low-confidence call is visible in the run rather than hidden in the output. The test replaces the network call with a fixed answer.

```
TYPESAFE_API_KEY=... squeegee run examples/words_2022.py --input examples/words-2022.txt --output /tmp/words-2022.json --db /tmp/squeegee-words.db
```

```
run 1 finished: 38 in, 37 out, 1 dropped, 0 errored, 0.03s
recorded in /tmp/squeegee-words.db
```

The timing above predates the classifier; expect a few seconds more for thirty-eight calls.

Thirty-eight blocks in, because the title is a record of its own, and thirty-seven dated entries out. The output is JSON rather than CSV: a record holds a list of quotes, and the CSV writer would flatten it into a string.
