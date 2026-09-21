import type { Status } from "./api";

const STATUSES: Status[] = ["ok", "dropped", "error"];

/** A whole number from the query string, or null when it is absent or nonsense. */
export function integerParam(params: URLSearchParams, name: string): number | null {
  const raw = params.get(name);
  if (raw === null || raw.trim() === "") return null;
  const value = Number(raw);
  return Number.isInteger(value) && value >= 0 ? value : null;
}

/** A status from the query string, or null when it is absent or not a status. */
export function statusParam(params: URLSearchParams, name: string): Status | null {
  const raw = params.get(name);
  return STATUSES.find((status) => status === raw) ?? null;
}
