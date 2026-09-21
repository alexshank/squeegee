import { afterEach, expect, test, vi } from "vitest";
import { ApiError, api } from "./api";

function stub(body: unknown, ok = true) {
  const fetched: string[] = [];
  vi.stubGlobal("fetch", (url: string) => {
    fetched.push(url);
    return Promise.resolve({ ok, json: () => Promise.resolve(body) } as Response);
  });
  return fetched;
}

afterEach(() => vi.unstubAllGlobals());

test("parameters that were not given are left out of the query", async () => {
  const fetched = stub({ items: [], next_cursor: null, has_more: false });

  await api.stageRecords(2, 1, { status: "error", limit: 50 });

  expect(fetched[0]).toBe("/api/runs/2/stages/1/records?status=error&limit=50");
});

test("a request with no parameters has no query string", async () => {
  const fetched = stub({ run_count: 0 });

  await api.meta();

  expect(fetched[0]).toBe("/api/meta");
});

test("a cursor is passed through so pagination can continue", async () => {
  const fetched = stub({ items: [], next_cursor: null, has_more: false });

  await api.stageRecords(2, 1, { cursor: "1042" });

  expect(fetched[0]).toContain("cursor=1042");
});

test("a field name is percent encoded into the path", async () => {
  const fetched = stub({ field: "a b", inferred_type: "string" });

  await api.field(1, 0, "a b/c");

  expect(fetched[0]).toBe("/api/runs/1/stages/0/fields/a%20b%2Fc");
});

test("the error envelope becomes an ApiError carrying its code", async () => {
  stub(
    {
      error: { code: "invalid_parameter", message: "limit must be at least 1", parameter: "limit" },
    },
    false,
  );

  await expect(api.runs({ limit: 0 })).rejects.toMatchObject({
    name: "ApiError",
    code: "invalid_parameter",
    parameter: "limit",
    message: "limit must be at least 1",
  });
});

test("a response without an envelope still throws something useful", async () => {
  vi.stubGlobal("fetch", () =>
    Promise.resolve({
      ok: false,
      statusText: "Bad Gateway",
      json: () => Promise.resolve({}),
    } as Response),
  );

  await expect(api.meta()).rejects.toBeInstanceOf(ApiError);
});
