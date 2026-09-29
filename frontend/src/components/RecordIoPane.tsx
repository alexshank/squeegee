import type { Trace } from "../api";
import { JsonValue } from "./JsonValue";
import { Empty, PaneHeading } from "./StagesPane";

interface Props {
  trace: Trace | null;
  error: string | null;
  position: number;
  recordIndex: number | null;
  onSource: (position: number) => void;
}

/** What the chosen stage was given and what it returned, for one record. */
export function RecordIoPane({ trace, error, position, recordIndex, onSource }: Props) {
  // the trace carries this stage's input and output, and unlike the records
  // table it is not limited to the page of records that is loaded
  const event = trace?.events.find((candidate) => candidate.position === position) ?? null;

  return (
    <section
      style={{
        borderTop: "1px solid var(--border)",
        // the records table is the one part of this column that may shrink, so
        // a wide record cannot squeeze it away
        flexShrink: 0,
        maxHeight: "50%",
        overflowY: "auto",
      }}
    >
      <PaneHeading>
        {recordIndex === null ? "record" : `record ${recordIndex} at this stage`}
      </PaneHeading>
      {recordIndex === null && <Empty>pick a record to see its input and output</Empty>}
      {recordIndex !== null && error !== null && <Empty>this record could not be loaded</Empty>}
      {recordIndex !== null && error === null && trace === null && <Empty>loading…</Empty>}
      {trace && !event && <Empty>{`record ${recordIndex} never reached this stage`}</Empty>}
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
