import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Status, Trace } from "../api";
import { JsonValue } from "./JsonValue";
import { Empty, PaneHeading } from "./StagesPane";
import { StatusPill } from "./StatusPill";

interface Props {
  trace: Trace | null;
  error: string | null;
  step: Status | null;
  onStep: (status: Status | null) => void;
  onRecord: (index: number) => void;
}

/** One record's whole journey, stage by stage, with changed fields marked. */
export function TracePane({ trace, error, step, onStep, onRecord }: Props) {
  if (!trace) {
    return (
      <aside style={{ borderLeft: "1px solid var(--border)" }}>
        <PaneHeading>trace</PaneHeading>
        {error ? (
          <p className="status-error" style={{ padding: "0 0.6rem" }}>
            {error}
          </p>
        ) : (
          <Empty>pick a record to trace it through the pipeline</Empty>
        )}
      </aside>
    );
  }

  return (
    <aside style={{ borderLeft: "1px solid var(--border)", overflowY: "auto" }}>
      <PaneHeading>{`record ${trace.record_index}`}</PaneHeading>
      <div
        style={{
          display: "flex",
          gap: "0.3rem",
          padding: "0 0.6rem 0.5rem",
          alignItems: "center",
        }}
      >
        <StepButton
          to={trace.previous_record_index}
          onRecord={onRecord}
          label={`previous ${step ?? "record"}`}
        >
          <ChevronLeft size={12} aria-hidden />
        </StepButton>
        <StepButton
          to={trace.next_record_index}
          onRecord={onRecord}
          label={`next ${step ?? "record"}`}
        >
          <ChevronRight size={12} aria-hidden />
        </StepButton>
        {/* stepping follows where a record ended up, which is a different question
            from what one stage did to it, so it carries its own filter */}
        <label style={{ color: "var(--muted)", fontSize: "0.72rem" }}>
          step through{" "}
          <select
            value={step ?? ""}
            onChange={(event) => onStep((event.target.value || null) as Status | null)}
            style={{
              background: "var(--bg)",
              color: "var(--text)",
              border: "1px solid var(--border)",
              font: "inherit",
              fontSize: "0.72rem",
            }}
          >
            <option value="">every record</option>
            <option value="ok">ok only</option>
            <option value="dropped">dropped only</option>
            <option value="error">errored only</option>
          </select>
        </label>
      </div>

      <div style={{ padding: "0 0.6rem 0.6rem" }}>
        <Label>as read</Label>
        <JsonValue value={trace.source} />
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

function Label({ children }: { children: string }) {
  return (
    <div
      style={{
        fontSize: "0.65rem",
        textTransform: "uppercase",
        letterSpacing: "0.06em",
        color: "var(--muted)",
      }}
    >
      {children}
    </div>
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
        display: "flex",
        alignItems: "center",
        gap: "0.2rem",
        border: "1px solid var(--border)",
        background: "none",
        color: to === null ? "var(--muted)" : "var(--text)",
        cursor: to === null ? "default" : "pointer",
        font: "inherit",
        fontSize: "0.72rem",
        padding: "0.05rem 0.4rem",
      }}
    >
      {children}
      {label}
    </button>
  );
}
