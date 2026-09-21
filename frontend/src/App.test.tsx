import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { App } from "./App";

const RUN = {
  run_id: 2,
  script_path: "/work/clean_orders.py",
  input_path: "orders.csv",
  output_path: null,
  started_at: "2026-09-20T17:22:44.039048Z",
  ended_at: "2026-09-20T17:22:44.539048Z",
  duration_us: 500000,
  status: "failed",
  stage_count: 2,
  records_in: 9,
  records_out: 0,
  records_dropped: 4,
  records_errored: 1,
  script_sha256: "9f2c",
  squeegee_version: "0.0.0",
  python_version: "3.12.4",
  options: { continue_on_error: false },
  failure: {
    stage_position: 1,
    stage_name: "parse_amount",
    record_index: 8,
    error_type: "ValueError",
    error_message: "could not convert string to float: 'n/a'",
  },
  stages: [
    {
      position: 0,
      name: "normalize_headers",
      description: "Lowercase the headers.",
      records_in: 9,
      records_ok: 9,
      records_dropped: 0,
      records_errored: 0,
      duration_us_total: 200,
      duration_us_median: 22,
      duration_us_p95: 30,
    },
    {
      position: 1,
      name: "parse_amount",
      description: "To cents.",
      records_in: 9,
      records_ok: 8,
      records_dropped: 0,
      records_errored: 1,
      duration_us_total: 400,
      duration_us_median: 38,
      duration_us_p95: 61,
    },
  ],
};

const STAGE = {
  ...RUN.stages[1],
  stage_version_id: 7,
  input_type: null,
  output_type: null,
  source_text: "@stage\ndef parse_amount(record):\n    return record\n",
  source_sha256: "4b81c2aa",
  source_language: "python",
  first_seen_at: "2026-09-14T09:31:02Z",
  also_used_by_runs: [1, 3],
};

const RECORDS = {
  items: [
    {
      record_index: 7,
      status: "ok",
      input: { id: "1007", amount: "$5.00" },
      output: { id: "1007", amount_cents: 500 },
      error_type: null,
      error_message: null,
      duration_us: 37,
    },
    {
      record_index: 8,
      status: "error",
      input: { id: "1008", amount: "n/a" },
      output: null,
      error_type: "ValueError",
      error_message: "could not convert string to float: 'n/a'",
      duration_us: 41,
    },
  ],
  next_cursor: null,
  has_more: false,
};

const TRACE = {
  record_index: 8,
  source: { "Order ID": "1008", Amount: "n/a" },
  final_status: "error",
  previous_record_index: 7,
  next_record_index: null,
  events: [
    {
      position: 0,
      stage_name: "normalize_headers",
      status: "ok",
      input: { "Order ID": "1008", Amount: "n/a" },
      output: { order_id: "1008", amount: "n/a" },
      changed_fields: ["Amount", "Order ID", "amount", "order_id"],
      error_type: null,
      error_message: null,
      duration_us: 22,
    },
    {
      position: 1,
      stage_name: "parse_amount",
      status: "error",
      input: { order_id: "1008", amount: "n/a" },
      output: null,
      changed_fields: [],
      error_type: "ValueError",
      error_message: "could not convert string to float: 'n/a'",
      duration_us: 41,
    },
  ],
};

const FIELDS = {
  records_considered: 8,
  items: [
    {
      field: "amount_cents",
      inferred_type: "number",
      non_null_count: 8,
      null_count: 0,
      distinct_count: 8,
      min: 400,
      max: 129900,
      mean: 21000,
      median: 2999,
      sum: 168000,
    },
  ],
};

const FIELD_DETAIL = {
  field: "amount_cents",
  inferred_type: "number",
  after: {
    stats: FIELDS.items[0],
    histogram: [{ lower: 400, upper: 65000, count: 7 }],
    top_values: null,
  },
  before: null,
};

function respond(body: unknown, ok = true) {
  return Promise.resolve({ ok, json: () => Promise.resolve(body) } as Response);
}

function stubApi(overrides: Record<string, unknown> = {}) {
  vi.stubGlobal("fetch", (url: string) => {
    const path = url.replace(/^\/api/, "");
    for (const [fragment, body] of Object.entries(overrides)) {
      if (path.startsWith(fragment)) return respond(body);
    }
    if (path.startsWith("/meta")) {
      return respond({ squeegee_version: "0.0.0", database_path: "/tmp/db", run_count: 1 });
    }
    if (/^\/runs\/\d+\/stages\/\d+\/fields\/.+/.test(path)) return respond(FIELD_DETAIL);
    if (/^\/runs\/\d+\/stages\/\d+\/fields/.test(path)) return respond(FIELDS);
    if (/^\/runs\/\d+\/stages\/\d+\/records/.test(path)) return respond(RECORDS);
    if (/^\/runs\/\d+\/stages\/\d+/.test(path)) return respond(STAGE);
    if (/^\/runs\/\d+\/records\/\d+/.test(path)) return respond(TRACE);
    if (/^\/runs\/\d+/.test(path)) return respond(RUN);
    return respond({ items: [RUN], next_cursor: null, has_more: false });
  });
}

beforeEach(() => window.history.pushState({}, "", "/"));
afterEach(() => vi.unstubAllGlobals());

test("the runs list opens a run", async () => {
  stubApi();
  render(<App />);

  const script = await screen.findByText("clean_orders.py");
  fireEvent.click(script);

  await waitFor(() => expect(screen.getByText(/run 2 ·/)).toBeDefined());
  expect(window.location.pathname).toBe("/runs/2");
});

test("a failed run leads with its failure", async () => {
  window.history.pushState({}, "", "/runs/2");
  stubApi();
  render(<App />);

  const banner = await screen.findByText(/failed at stage 1/);
  expect(banner.className).toBe("status-error");
  expect(banner.textContent).toContain("could not convert string to float: 'n/a'");
});

test("showing the failure selects its stage and record", async () => {
  window.history.pushState({}, "", "/runs/2");
  stubApi();
  render(<App />);

  fireEvent.click(await screen.findByText("show it"));

  await waitFor(() => expect(window.location.search).toContain("stage=1"));
  expect(window.location.search).toContain("record=8");
});

test("the three panes are on screen at once", async () => {
  window.history.pushState({}, "", "/runs/2?stage=1&record=8");
  stubApi();
  render(<App />);

  expect((await screen.findAllByText("0 normalize_headers")).length).toBe(2);
  // prism splits the source into one span per token, so the header identifies the panel
  expect(await screen.findByText(/parse_amount · 4b81c2aa/)).toBeDefined();
  expect(document.querySelector("pre")).not.toBeNull();
  expect(await screen.findByText("record 8")).toBeDefined();
});

test("the trace marks the fields a stage changed", async () => {
  window.history.pushState({}, "", "/runs/2?stage=1&record=8");
  stubApi();
  render(<App />);

  const trace = await screen.findByText("record 8");
  const pane = trace.parentElement as HTMLElement;
  const changed = within(pane).getByText("order_id");

  expect(changed.style.textDecoration).toBe("underline");
});

test("status is shown with a glyph, not colour alone", async () => {
  window.history.pushState({}, "", "/runs/2?stage=1");
  stubApi();
  render(<App />);

  const pills = await screen.findAllByText(/✕ error/);
  expect(pills.length).toBeGreaterThan(0);
});

test("filtering by status puts the filter in the URL", async () => {
  window.history.pushState({}, "", "/runs/2?stage=1");
  stubApi();
  render(<App />);

  fireEvent.click(await screen.findByText("dropped"));

  await waitFor(() => expect(window.location.search).toContain("status=dropped"));
});

test("choosing a field shows its statistics", async () => {
  window.history.pushState({}, "", "/runs/2?stage=1");
  stubApi();
  render(<App />);

  fireEvent.click(await screen.findByText("amount_cents"));

  expect(
    await screen.findByText("This stage created the field; there is nothing to compare against."),
  ).toBeDefined();
});
