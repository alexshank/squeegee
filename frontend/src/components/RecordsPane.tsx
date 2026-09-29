import { useEffect, useState } from "react";
import { activate } from "../RunsList";
import type { RecordEvent, Status } from "../api";
import { Empty } from "./StagesPane";
import { StatusPill } from "./StatusPill";

const STATUSES: (Status | null)[] = [null, "ok", "dropped", "error"];

interface Props {
  records: RecordEvent[];
  hasMore: boolean;
  loading: boolean;
  error: string | null;
  status: Status | null;
  search: string;
  recordIndex: number | null;
  onStatus: (status: Status | null) => void;
  onSearch: (search: string) => void;
  onRecord: (index: number) => void;
  onLoadMore: () => void;
}

/** The records that passed through the chosen stage. */
export function RecordsPane(props: Props) {
  const { records, hasMore, loading, error, status, search, recordIndex } = props;
  const typed = useDebouncedSearch(search, props.onSearch);
  return (
    <section style={{ overflowY: "auto", padding: "0 0.75rem 1rem" }}>
      <div
        style={{
          display: "flex",
          gap: "0.4rem",
          alignItems: "center",
          padding: "0.5rem 0",
          flexWrap: "wrap",
        }}
      >
        {STATUSES.map((option) => (
          <button
            key={option ?? "all"}
            type="button"
            onClick={() => props.onStatus(option)}
            style={{
              border: `1px solid ${option === status ? "var(--accent)" : "var(--border)"}`,
              background: "none",
              color: "var(--text)",
              cursor: "pointer",
              font: "inherit",
              fontSize: "0.75rem",
              padding: "0.1rem 0.5rem",
            }}
          >
            {option ?? "all"}
          </button>
        ))}
        <input
          value={typed.value}
          placeholder="search stored JSON"
          onChange={(event) => typed.onChange(event.target.value)}
          style={{
            flex: 1,
            minWidth: "12rem",
            border: "1px solid var(--border)",
            background: "var(--bg)",
            color: "var(--text)",
            font: "inherit",
            fontSize: "0.75rem",
            padding: "0.15rem 0.4rem",
          }}
        />
      </div>

      {error && <p className="status-error">{error}</p>}
      {!loading && records.length === 0 && <Empty>no records match</Empty>}
      {records.length > 0 && (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
          <thead>
            <tr style={{ textAlign: "left", color: "var(--muted)", fontSize: "0.7rem" }}>
              <th style={{ padding: "0.25rem" }}>#</th>
              <th style={{ padding: "0.25rem" }}>status</th>
              <th style={{ padding: "0.25rem", textAlign: "right" }}>time</th>
            </tr>
          </thead>
          <tbody>
            {records.map((event) => (
              <tr
                key={event.record_index}
                tabIndex={0}
                onClick={() => props.onRecord(event.record_index)}
                onKeyDown={(pressed) => activate(pressed, () => props.onRecord(event.record_index))}
                style={{
                  borderTop: "1px solid var(--border)",
                  cursor: "pointer",
                  background: event.record_index === recordIndex ? "var(--surface)" : "transparent",
                }}
              >
                <td style={{ padding: "0.25rem", fontFamily: "var(--mono)" }}>
                  {event.record_index}
                </td>
                <td style={{ padding: "0.25rem" }}>
                  <StatusPill status={event.status} />
                </td>
                <td style={{ padding: "0.25rem", textAlign: "right", fontFamily: "var(--mono)" }}>
                  {event.duration_us}µs
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          padding: "0.4rem 0",
          color: "var(--muted)",
          fontSize: "0.75rem",
        }}
      >
        <span>
          {records.length} record{records.length === 1 ? "" : "s"}
          {hasMore ? " so far" : ""}
        </span>
        {hasMore && (
          <button
            type="button"
            onClick={props.onLoadMore}
            disabled={loading}
            style={{
              border: "1px solid var(--border)",
              background: "none",
              color: "var(--text)",
              cursor: loading ? "default" : "pointer",
              font: "inherit",
              fontSize: "0.75rem",
              padding: "0.1rem 0.5rem",
            }}
          >
            {loading ? "loading…" : "load more"}
          </button>
        )}
      </div>
    </section>
  );
}

/**
 * Hold what the developer typed locally and report it once they pause.
 *
 * Reporting every keystroke would mean one request and one history entry per
 * character, which turns the Back button into a way to retype the search.
 */
function useDebouncedSearch(search: string, onSearch: (search: string) => void) {
  const [value, setValue] = useState(search);
  const [pending, setPending] = useState<string | null>(null);

  useEffect(() => setValue(search), [search]);

  useEffect(() => {
    if (pending === null) return;
    const timer = setTimeout(() => {
      onSearch(pending);
      setPending(null);
    }, 250);
    return () => clearTimeout(timer);
  }, [pending, onSearch]);

  return {
    value,
    onChange: (next: string) => {
      setValue(next);
      setPending(next);
    },
  };
}
