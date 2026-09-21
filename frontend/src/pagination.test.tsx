import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { RunView } from "./RunView";

const STAGE = {
  position: 0,
  name: "normalize_headers",
  description: "Lowercase the headers.",
  records_in: 4,
  records_ok: 4,
  records_dropped: 0,
  records_errored: 0,
  duration_us_total: 100,
  duration_us_median: 20,
  duration_us_p95: 30,
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
  records_in: 4,
  records_out: 4,
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

interface Options {
  recordsFail?: boolean;
}

function stubApi({ recordsFail = false }: Options = {}) {
  const requested: string[] = [];
  vi.stubGlobal("fetch", (url: string) => {
    requested.push(url);
    const respond = (body: unknown, ok = true) =>
      Promise.resolve({ ok, json: () => Promise.resolve(body) } as Response);

    if (url.includes("/records")) {
      if (recordsFail) {
        return respond({ error: { code: "not_found", message: "no such stage" } }, false);
      }
      if (url.includes("status=dropped")) {
        return respond({ items: [event(3, "dropped")], next_cursor: null, has_more: false });
      }
      return url.includes("cursor=2")
        ? respond({ items: [event(2), event(3)], next_cursor: null, has_more: false })
        : respond({ items: [event(0), event(1)], next_cursor: "2", has_more: true });
    }
    if (url.includes("/fields")) return respond({ records_considered: 4, items: [] });
    if (url.includes("/stages/0")) return respond(STAGE);
    if (url.includes("/records/")) return respond(null);
    return respond(RUN);
  });
  return requested;
}

beforeEach(() => window.history.pushState({}, "", "/runs/1?stage=0"));
afterEach(() => vi.unstubAllGlobals());

function renderRun() {
  return render(<RunView runId={1} params={new URLSearchParams(window.location.search)} />);
}

test("a further page is fetched with the cursor and appended", async () => {
  const requested = stubApi();
  renderRun();

  await screen.findByText("0");
  expect(screen.getByText("2 records so far")).toBeDefined();

  fireEvent.click(screen.getByText("load more"));

  await waitFor(() => expect(screen.getByText("3")).toBeDefined());
  expect(requested.some((url) => url.includes("cursor=2"))).toBe(true);
  // the first page is still on screen: pages accumulate rather than replace
  expect(screen.getByText("0")).toBeDefined();
});

test("the load more button goes away once the last page arrives", async () => {
  stubApi();
  renderRun();

  fireEvent.click(await screen.findByText("load more"));

  await waitFor(() => expect(screen.queryByText("load more")).toBeNull());
  expect(screen.getByText("4 records")).toBeDefined();
});

test("changing a filter starts the pages over without a cursor", async () => {
  const requested = stubApi();
  renderRun();

  fireEvent.click(await screen.findByText("load more"));
  await waitFor(() => expect(screen.getByText("3")).toBeDefined());

  fireEvent.click(screen.getByText("dropped"));
  // the view re-renders from the URL the setter wrote
  render(<RunView runId={1} params={new URLSearchParams("stage=0&status=dropped")} />);

  await waitFor(() => expect(screen.getAllByText("1 record").length).toBeGreaterThan(0));
  const filtered = requested.filter((url) => url.includes("status=dropped"));
  expect(filtered.every((url) => !url.includes("cursor="))).toBe(true);
});

test("a failed page shows the error instead of an empty table", async () => {
  stubApi({ recordsFail: true });
  renderRun();

  expect(await screen.findByText("no such stage")).toBeDefined();
});
