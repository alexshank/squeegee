import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "./App";

function respond(body: unknown, ok = true) {
  return Promise.resolve({ ok, json: () => Promise.resolve(body) } as Response);
}

afterEach(() => vi.unstubAllGlobals());

test("the shell lists the runs it loads", async () => {
  vi.stubGlobal("fetch", (url: string) =>
    url.includes("/meta")
      ? respond({ squeegee_version: "0.0.0", database_path: "/tmp/db", run_count: 1 })
      : respond({
          items: [
            {
              run_id: 2,
              script_path: "/work/clean_orders.py",
              status: "failed",
              records_in: 9,
              records_out: 0,
              records_dropped: 4,
              records_errored: 1,
            },
          ],
          next_cursor: null,
          has_more: false,
        }),
  );

  render(<App />);

  await waitFor(() => expect(screen.getByText("clean_orders.py")).toBeDefined());
  expect(screen.getByText("failed").className).toBe("status-error");
  expect(screen.getByText("/tmp/db", { exact: false })).toBeDefined();
});

test("an API error is shown rather than swallowed", async () => {
  vi.stubGlobal("fetch", () =>
    respond({ error: { code: "not_found", message: "no run 99", parameter: null } }, false),
  );

  render(<App />);

  await waitFor(() => expect(screen.getByText("no run 99")).toBeDefined());
});
