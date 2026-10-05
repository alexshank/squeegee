// one test per finding from the review of this work, so none of them come back

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { App } from "./App";
import { RunView } from "./RunView";
import { StageSource } from "./components/StageSource";

const STAGE = {
  position: 0,
  name: "normalize_headers",
  description: "Lowercase the headers.",
  records_in: 3,
  records_ok: 3,
  records_dropped: 0,
  records_errored: 0,
  duration_us_total: 60,
  duration_us_median: 20,
  duration_us_p95: 25,
  stage_version_id: 1,
  input_type: null,
  output_type: null,
  source_text: "@stage\ndef normalize_headers(record):\n    return record\n",
  source_sha256: "aaaabbbb",
  source_language: "python",
  first_seen_at: "2026-09-14T09:31:02Z",
  also_used_by_runs: [],
};

const RUN = {
  run_id: 1,
  script_path: "/work/clean_orders.py",
  input_path: "orders.csv",
  output_path: null,
  started_at: "2026-09-20T17:22:38Z",
  ended_at: "2026-09-20T17:22:41Z",
  duration_us: 3000000,
  status: "finished",
  stage_count: 1,
  records_in: 3,
  records_out: 3,
  records_dropped: 0,
  records_errored: 0,
  script_sha256: "9f2c",
  squeegee_version: "0.0.0",
  python_version: "3.12.4",
  options: {},
  failure: null,
  stages: [STAGE],
};

function event(index: number, status = "ok") {
  return {
    record_index: index,
    status,
    input: { id: String(index) },
    output: status === "ok" ? { id: String(index) } : null,
    error_type: null,
    error_message: null,
    duration_us: 20,
  };
}

function deferred<Value>() {
  let resolve: (value: Value) => void = () => undefined;
  const promise = new Promise<Value>((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

function ok(body: unknown) {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
}

function failed(message: string) {
  return Promise.resolve({
    ok: false,
    json: () => Promise.resolve({ error: { code: "not_found", message, parameter: null } }),
  } as Response);
}

interface Stubs {
  records?: (url: string) => Promise<Response>;
  trace?: (url: string) => Promise<Response>;
  fieldDetail?: unknown;
}

function stubApi(stubs: Stubs = {}) {
  const requested: string[] = [];
  vi.stubGlobal("fetch", (url: string) => {
    requested.push(url);
    if (/\/fields\/.+/.test(url)) return ok(stubs.fieldDetail ?? null);
    if (url.includes("/fields")) {
      return ok({
        records_considered: 3,
        items: [
          {
            field: "id",
            inferred_type: "mixed",
            non_null_count: 3,
            null_count: 0,
            distinct_count: 3,
            min: null,
            max: null,
            mean: null,
            median: null,
            sum: null,
          },
        ],
      });
    }
    if (url.includes("/records/")) {
      return stubs.trace ? stubs.trace(url) : ok(null);
    }
    if (url.includes("/records")) {
      return stubs.records
        ? stubs.records(url)
        : ok({ items: [event(0)], next_cursor: null, has_more: false });
    }
    if (/\/stages\/\d+/.test(url)) return ok(STAGE);
    return ok(RUN);
  });
  return requested;
}

function trace(index: number) {
  return {
    record_index: index,
    source: { id: String(index) },
    final_status: "ok",
    previous_record_index: null,
    next_record_index: null,
    events: [
      {
        position: 0,
        stage_name: "normalize_headers",
        status: "ok",
        input: { id: `in-${index}` },
        output: { id: `out-${index}` },
        changed_fields: [],
        error_type: null,
        error_message: null,
        duration_us: 20,
      },
    ],
  };
}

function renderRun(query: string) {
  window.history.pushState({}, "", `/runs/1?${query}`);
  return render(<RunView runId={1} params={new URLSearchParams(query)} />);
}

beforeEach(() => window.history.pushState({}, "", "/runs/1"));
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

test("a page that arrives after the filter changed is discarded", async () => {
  const secondPage = deferred<Response>();
  const requested = stubApi({
    records: (url) => {
      if (url.includes("status=dropped")) {
        return ok({ items: [event(9, "dropped")], next_cursor: null, has_more: false });
      }
      if (url.includes("cursor=")) {
        // the second page is still in flight when the filter changes
        return secondPage.promise;
      }
      return ok({ items: [event(0), event(1)], next_cursor: "2", has_more: true });
    },
  });
  const view = renderRun("stage=0");

  fireEvent.click(await screen.findByText("load more"));
  view.rerender(<RunView runId={1} params={new URLSearchParams("stage=0&status=dropped")} />);
  await waitFor(() => expect(screen.getByText("9")).toBeDefined());

  secondPage.resolve({
    ok: true,
    json: () =>
      Promise.resolve({ items: [event(2), event(3)], next_cursor: null, has_more: false }),
  } as Response);
  await Promise.resolve();

  // the stale page must not append ok records onto a dropped-only list
  await waitFor(() => expect(screen.getByText("1 record")).toBeDefined());
  expect(document.querySelectorAll("tbody tr").length).toBe(1);
  expect(requested.some((url) => url.includes("cursor="))).toBe(true);
});

test("a trace that fails to load says so instead of showing the empty state", async () => {
  stubApi({ trace: () => failed("run 1 has no record 999") });
  renderRun("stage=0&record=999");

  expect(await screen.findByText("run 1 has no record 999")).toBeDefined();
  expect(screen.queryByText("pick a record to trace it through the pipeline")).toBeNull();
});

test("a trace still loading never appears under the newly chosen record", async () => {
  const second = deferred<Response>();
  let call = 0;
  stubApi({
    trace: () => (call++ === 0 ? ok(trace(7)) : second.promise),
    records: () => ok({ items: [event(7), event(8)], next_cursor: null, has_more: false }),
  });
  const view = renderRun("stage=0&record=7");
  await waitFor(() => expect(screen.getAllByText(/in-7/).length).toBeGreaterThan(0));

  view.rerender(<RunView runId={1} params={new URLSearchParams("stage=0&record=8")} />);

  // useApi keeps record 7's trace in hand while record 8's request is open
  expect(screen.getByText("record 8 at stage 0")).toBeDefined();
  expect(screen.queryAllByText(/in-7/)).toEqual([]);
  expect(screen.queryByText("record 7")).toBeNull();

  second.resolve({ ok: true, json: () => Promise.resolve(trace(8)) } as Response);

  await waitFor(() => expect(screen.getAllByText(/in-8/).length).toBeGreaterThan(0));
  expect(screen.getByText("record 8")).toBeDefined();
});

test("an invalid stage position is still reported at the top of the run", async () => {
  vi.stubGlobal("fetch", (url: string) => {
    if (url.includes("/fields")) return failed("run 1 has no stage at position 9");
    if (url.includes("/records")) return ok({ items: [], next_cursor: null, has_more: false });
    return ok(RUN);
  });
  renderRun("stage=9");

  // the run view no longer asks for stage detail, so the field request is what
  // now carries the message to the problems list
  expect(await screen.findByText("run 1 has no stage at position 9")).toBeDefined();
});

test("a stage whose source fails to load says so in the modal", async () => {
  vi.stubGlobal("fetch", (url: string) => {
    if (/\/stages\/\d+$/.test(url)) return failed("run 1 has no stage at position 9");
    if (url.includes("/records")) return ok({ items: [], next_cursor: null, has_more: false });
    if (url.includes("/fields")) return ok({ records_considered: 0, items: [] });
    return ok(RUN);
  });
  renderRun("stage=0&source=9");

  expect(await screen.findByText("run 1 has no stage at position 9")).toBeDefined();
});

test("typing in the search box asks once, and leaves one history entry", async () => {
  vi.useFakeTimers();
  const requested = stubApi();
  window.history.pushState({}, "", "/runs/1?stage=0");
  render(<App />);
  await vi.advanceTimersByTimeAsync(0);
  const historyBefore = window.history.length;

  const box = screen.getByPlaceholderText("search inputs and outputs");
  for (const value of ["n", "n/", "n/a"]) {
    fireEvent.change(box, { target: { value } });
    await vi.advanceTimersByTimeAsync(50);
  }
  await vi.advanceTimersByTimeAsync(300);

  expect(requested.filter((url) => url.includes("q=")).length).toBe(1);
  expect(requested.some((url) => url.includes("q=n%2Fa"))).toBe(true);
  expect(window.history.length).toBe(historyBefore);
});

test("nonsense parameters are ignored rather than requested", async () => {
  const requested = stubApi();
  renderRun("stage=x&record=&status=banana");

  await waitFor(() => expect(requested.some((url) => url.includes("/records"))).toBe(true));

  expect(requested.some((url) => url.includes("NaN"))).toBe(false);
  expect(requested.some((url) => url.includes("status=banana"))).toBe(false);
  // an empty record parameter is not record 0
  expect(requested.some((url) => /\/records\/\d/.test(url))).toBe(false);
  // an unparseable stage falls back to the first one
  expect(requested.some((url) => url.includes("/stages/0"))).toBe(true);
});

test("stepping walks the records table, so the trace carries the table's filters", async () => {
  const requested = stubApi({ trace: () => ok(trace(4)) });
  renderRun("stage=0&status=error&q=n%2Fa&record=4");

  await waitFor(() => expect(screen.getByText("record 4")).toBeDefined());

  const traced = requested.find((url) => /\/records\/4/.test(url));
  expect(traced).toContain("stage=0");
  expect(traced).toContain("status=error");
  expect(traced).toContain("q=n%2Fa");
});

// a two row table that both stubbed endpoints filter the way the server does
const TABLE = [
  { index: 1, status: "ok", text: "apple" },
  { index: 2, status: "dropped", text: "banana" },
];

function rowsFor(url: string) {
  const query = new URL(url, "http://squeegee").searchParams;
  return TABLE.filter(
    (row) =>
      (!query.get("status") || row.status === query.get("status")) &&
      (!query.get("q") || row.text.includes(query.get("q") ?? "")),
  );
}

function stubTable(slowTrace: (url: string) => Promise<Response> | null = () => null) {
  const requested = stubApi({
    records: (url) =>
      ok({
        items: rowsFor(url).map((row) => event(row.index, row.status)),
        next_cursor: null,
        has_more: false,
      }),
    trace: (url) => {
      const index = Number(/records\/(\d+)/.exec(url)?.[1]);
      return (
        slowTrace(url) ??
        ok({ ...trace(index), listed: rowsFor(url).some((row) => row.index === index) })
      );
    },
  });
  window.history.pushState({}, "", "/runs/1?stage=0&record=1");
  render(<App />);
  return requested;
}

// let every settled request's then() run, so the assertion follows the answer
const settle = () => new Promise((resolve) => setTimeout(resolve, 20));

test("a filter that still lists the chosen record keeps it", async () => {
  const requested = stubTable();
  await waitFor(() => expect(screen.getByText("record 1")).toBeDefined());

  fireEvent.click(screen.getByRole("button", { name: "ok" }));

  // refilter asks for one row of the filtered table once it has the answer in hand
  await waitFor(() => expect(requested.some((url) => url.includes("limit=1"))).toBe(true));
  await settle();
  expect(window.location.search).toContain("status=ok");
  expect(window.location.search).toContain("record=1");
});

test("an answer for a filter already replaced is ignored", async () => {
  const slow = deferred<Response>();
  stubTable((url) => (url.includes("status=dropped") ? slow.promise : null));
  await waitFor(() => expect(screen.getByText("record 1")).toBeDefined());

  fireEvent.click(screen.getByRole("button", { name: "dropped" }));
  fireEvent.click(screen.getByRole("button", { name: "all" }));
  await settle();
  // had it been heeded, this answer would move the selection to record 2
  slow.resolve({
    ok: true,
    json: () => Promise.resolve({ ...trace(1), listed: false }),
  } as Response);
  await settle();

  expect(window.location.search).toContain("record=1");
  expect(window.location.search).not.toContain("status=");
});

test("a filter that hides the chosen record moves to its first record", async () => {
  stubTable();
  await waitFor(() => expect(screen.getByText("record 1")).toBeDefined());

  fireEvent.click(screen.getByRole("button", { name: "dropped" }));

  await waitFor(() => expect(window.location.search).toContain("record=2"));
  expect(window.location.search).toContain("status=dropped");
});

test("a filter that lists nothing returns the trace to its placeholder", async () => {
  stubTable();
  await waitFor(() => expect(screen.getByText("record 1")).toBeDefined());

  fireEvent.click(screen.getByRole("button", { name: "error" }));

  await waitFor(() =>
    expect(screen.getByText("pick a record to trace it through the pipeline")).toBeDefined(),
  );
  expect(window.location.search).not.toContain("record=");
});

test("a search that hides the chosen record moves to its first match", async () => {
  stubTable();
  await waitFor(() => expect(screen.getByText("record 1")).toBeDefined());

  fireEvent.change(screen.getByPlaceholderText("search inputs and outputs"), {
    target: { value: "banana" },
  });

  await waitFor(() => expect(window.location.search).toContain("record=2"));
  expect(window.location.search).toContain("q=banana");
});

test("top values of mixed types do not collide as React keys", async () => {
  const warnings: unknown[] = [];
  vi.spyOn(console, "error").mockImplementation((...args) => warnings.push(args[0]));
  stubApi({
    fieldDetail: {
      field: "id",
      inferred_type: "mixed",
      after: {
        stats: {
          field: "id",
          inferred_type: "mixed",
          non_null_count: 2,
          null_count: 0,
          distinct_count: 2,
          min: null,
          max: null,
          mean: null,
          median: null,
          sum: null,
        },
        histogram: null,
        // sqlite groups the number and the string separately
        top_values: [
          { value: 1, count: 3 },
          { value: "1", count: 2 },
        ],
      },
      before: null,
    },
  });
  renderRun("stage=0&field=id");

  await waitFor(() => expect(screen.getAllByText("1").length).toBeGreaterThan(0));

  expect(warnings.filter((warning) => String(warning).includes("same key")).length).toBe(0);
});

test("the code block takes its colours from the UI variables", () => {
  render(<StageSource source={STAGE.source_text} name="normalize_headers" sha="aaaabbbb" />);

  const block = document.querySelector("pre");

  expect(block?.style.color).toBe("var(--text)");
  expect(block?.style.backgroundColor).toBe("transparent");
});
