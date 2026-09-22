import { useEffect, useRef } from "react";
import type { Trace } from "../api";
import type { Loaded } from "../useApi";
import { JsonValue } from "./JsonValue";
import { Empty, PaneHeading } from "./StagesPane";

interface Props {
  trace: Loaded<Trace | null>;
  position: number;
  recordIndex: number | null;
  onSource: (position: number) => void;
}

/** What the chosen stage was given and what it returned, for one record. */
export function RecordIoPane({ trace, position, recordIndex, onSource }: Props) {
  const pane = useRef<HTMLElement>(null);

  // useApi keeps the last good value visible while the next one loads, so the
  // trace in hand may still be the record that was selected before this one
  const loaded = trace.data?.record_index === recordIndex ? trace.data : null;
  // the trace carries this stage's input and output, and unlike the records
  // table it is not limited to the page of records that is loaded
  const event = loaded?.events.find((candidate) => candidate.position === position) ?? null;

  // the table above can be hundreds of rows long, so picking a record far down
  // it would otherwise change only what is below the fold
  useEffect(() => {
    if (recordIndex !== null) pane.current?.scrollIntoView({ block: "nearest" });
  }, [recordIndex]);

  return (
    <section ref={pane} style={{ borderTop: "1px solid var(--border)" }}>
      <PaneHeading>
        {recordIndex === null ? "record" : `record ${recordIndex} at this stage`}
      </PaneHeading>
      {recordIndex === null && <Empty>pick a record to see its input and output</Empty>}
      {recordIndex !== null && trace.error !== null && (
        <Empty>this record could not be loaded</Empty>
      )}
      {recordIndex !== null && trace.error === null && loaded === null && <Empty>loading…</Empty>}
      {loaded && !event && <Empty>{`record ${recordIndex} never reached this stage`}</Empty>}
      {event && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "1rem",
            padding: "0 0.75rem 0.75rem",
          }}
        >
          <div style={{ minWidth: 0 }}>
            <Label>input</Label>
            <JsonValue value={event.input} />
          </div>
          <div style={{ minWidth: 0 }}>
            <Label>output</Label>
            {event.status === "error" ? (
              <p
                className="status-error"
                style={{ margin: 0, fontFamily: "var(--mono)", fontSize: "0.8rem" }}
              >
                {event.error_type}: {event.error_message}{" "}
                <button
                  type="button"
                  onClick={() => onSource(position)}
                  style={{
                    background: "none",
                    border: "1px solid currentColor",
                    color: "inherit",
                    cursor: "pointer",
                    font: "inherit",
                    fontSize: "0.75rem",
                  }}
                >
                  view source
                </button>
              </p>
            ) : event.output ? (
              <JsonValue value={event.output} changed={event.changed_fields} />
            ) : (
              <p className="status-dropped" style={{ margin: 0 }}>
                dropped here
              </p>
            )}
          </div>
        </div>
      )}
    </section>
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
