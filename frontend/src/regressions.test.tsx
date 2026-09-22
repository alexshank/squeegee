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

  const box = screen.getByPlaceholderText("search stored JSON");
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

test("the record filter and the stepping filter are separate parameters", async () => {
  const requested = stubApi({
    records: () => ok({ items: [event(4, "error")], next_cursor: null, has_more: false }),
    trace: () =>
      ok({
        record_index: 4,
        source: { id: "4" },
        final_status: "dropped",
        previous_record_index: 2,
        next_record_index: null,
        events: [],
      }),
  });
  renderRun("stage=0&status=error&step=dropped&record=4");

  await waitFor(() => expect(screen.getByText("record 4")).toBeDefined());

  const records = requested.find((url) => url.includes("/records?"));
  const trace = requested.find((url) => /\/records\/4/.test(url));
  expect(records).toContain("status=error");
  expect(trace).toContain("status=dropped");
});

test("choosing what to step through writes only the step parameter", async () => {
  stubApi({
    trace: () =>
      ok({
        record_index: 1,
        source: { id: "1" },
        final_status: "ok",
        previous_record_index: null,
        next_record_index: null,
        events: [],
      }),
  });
  renderRun("stage=0&status=error&record=1");

  fireEvent.change(await screen.findByDisplayValue("every record"), {
    target: { value: "dropped" },
  });

  await waitFor(() => expect(window.location.search).toContain("step=dropped"));
  expect(window.location.search).toContain("status=error");
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
