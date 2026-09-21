import { activate } from "../RunsList";
import type { RecordEvent, StageDetail, Status } from "../api";
import { StageSource } from "./StageSource";
import { Empty, PaneHeading } from "./StagesPane";
import { StatusPill } from "./StatusPill";

const STATUSES: (Status | null)[] = [null, "ok", "dropped", "error"];

interface Props {
  stage: StageDetail | null;
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

/** The records that passed through the chosen stage, and the code that did it. */
export function RecordsPane(props: Props) {
  const { stage, records, hasMore, loading, error, status, search, recordIndex } = props;
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
          value={search}
          placeholder="search stored JSON"
          onChange={(event) => props.onSearch(event.target.value)}
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
              <th style={{ padding: "0.25rem" }}>input</th>
              <th style={{ padding: "0.25rem" }}>output</th>
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
                <td style={{ padding: "0.25rem", maxWidth: "16rem" }}>
                  <Preview value={event.input} />
                </td>
                <td style={{ padding: "0.25rem", maxWidth: "16rem" }}>
                  {event.output ? (
                    <Preview value={event.output} />
                  ) : (
                    <span className={`status-${event.status}`}>
                      {event.error_message ?? "dropped"}
                    </span>
                  )}
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

      {stage && (
        <>
          <PaneHeading>source</PaneHeading>
          <StageSource source={stage.source_text} name={stage.name} sha={stage.source_sha256} />
          <p style={{ color: "var(--muted)", fontSize: "0.75rem" }}>
            {stage.input_type ?? "unannotated"} → {stage.output_type ?? "unannotated"}
            {stage.also_used_by_runs.length > 0 &&
              ` · unchanged since runs ${stage.also_used_by_runs.join(", ")}`}
          </p>
        </>
      )}
    </section>
  );
}

function Preview({ value }: { value: Record<string, unknown> }) {
  return (
    <span
      style={{
        fontFamily: "var(--mono)",
        fontSize: "0.75rem",
        color: "var(--muted)",
        display: "block",
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
      }}
    >
      {JSON.stringify(value)}
    </span>
  );
}
