import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Trace } from "../api";
import { JsonValue } from "./JsonValue";
import { Label } from "./RawValue";
import { Empty, PaneHeading } from "./StagesPane";
import { StatusPill } from "./StatusPill";

interface Props {
  trace: Trace | null;
  loading: boolean;
  error: string | null;
  onRecord: (index: number) => void;
}

/** One record's whole journey, stage by stage, with changed fields marked. */
export function TracePane({ trace, loading, error, onRecord }: Props) {
  if (!trace) {
    return (
      <aside>
        <PaneHeading>trace</PaneHeading>
        {error ? (
          <p className="status-error" style={{ padding: "0 0.6rem" }}>
            {error}
          </p>
        ) : loading ? (
          <Empty>loading…</Empty>
        ) : (
          <Empty>pick a record to trace it through the pipeline</Empty>
        )}
      </aside>
    );
  }

  return (
    <aside style={{ overflowY: "auto" }}>
      <PaneHeading>{`record ${trace.record_index}`}</PaneHeading>
      <div
        style={{
          display: "flex",
          gap: "0.3rem",
          padding: "0 0.6rem 0.5rem",
          alignItems: "center",
        }}
      >
        <StepButton to={trace.previous_record_index} onRecord={onRecord} label="previous record">
          <ChevronLeft size={14} aria-hidden />
          previous record
        </StepButton>
        <StepButton to={trace.next_record_index} onRecord={onRecord} label="next record">
          next record
          <ChevronRight size={14} aria-hidden />
        </StepButton>
      </div>

      {trace.events.map((event) => (
        <article
          key={event.position}
          style={{ borderTop: "1px solid var(--border)", padding: "0.5rem 0.6rem" }}
        >
          <header
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: "0.5rem",
              alignItems: "center",
              marginBottom: "0.35rem",
            }}
          >
            <span style={{ fontFamily: "var(--mono)", fontSize: "0.8rem" }}>
              {`${event.position} ${event.stage_name}`}
            </span>
            <span style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
              <StatusPill status={event.status} />
              <small style={{ color: "var(--muted)", fontFamily: "var(--mono)" }}>
                {event.duration_us}µs
              </small>
            </span>
          </header>
          {event.status === "error" ? (
            <p className="status-error" style={{ fontFamily: "var(--mono)", fontSize: "0.8rem" }}>
              {event.error_type}: {event.error_message}
            </p>
          ) : (
            <>
              <Label>output</Label>
              {event.output ? (
                <JsonValue value={event.output} changed={event.changed_fields} />
              ) : (
                <p className="status-dropped">dropped here</p>
              )}
            </>
          )}
        </article>
      ))}

      {trace.final_status !== "ok" && (
        <p style={{ padding: "0 0.6rem 1rem", color: "var(--muted)", fontSize: "0.75rem" }}>
          The trace ends here. Later stages never saw this record.
        </p>
      )}
    </aside>
  );
}

function StepButton({
  to,
  onRecord,
  label,
  children,
}: {
  to: number | null;
  onRecord: (index: number) => void;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      disabled={to === null}
      aria-label={label}
      onClick={() => to !== null && onRecord(to)}
      style={{
        flex: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "0.2rem",
        border: "1px solid var(--border)",
        background: "none",
        color: to === null ? "var(--muted)" : "var(--text)",
        cursor: to === null ? "default" : "pointer",
        font: "inherit",
        fontSize: "0.75rem",
        padding: "0.2rem 0.4rem",
      }}
    >
      {children}
    </button>
  );
}
