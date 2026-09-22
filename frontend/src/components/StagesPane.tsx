import { Code } from "lucide-react";
import type { FieldStats, StageSummary } from "../api";

interface Props {
  stages: StageSummary[];
  position: number;
  fields: FieldStats[];
  field: string | null;
  onStage: (position: number) => void;
  onField: (field: string | null) => void;
  onSource: (position: number) => void;
}

/** The pipeline in declaration order, and the fields the chosen stage produced. */
export function StagesPane({ stages, position, fields, field, onStage, onField, onSource }: Props) {
  return (
    <aside style={{ borderRight: "1px solid var(--border)", overflowY: "auto" }}>
      <PaneHeading>stages</PaneHeading>
      <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {stages.map((stage) => (
          <li key={stage.position} style={{ display: "flex", alignItems: "center" }}>
            <button
              type="button"
              onClick={() => onStage(stage.position)}
              aria-current={stage.position === position}
              style={rowStyle(stage.position === position)}
            >
              <span
                style={{ fontFamily: "var(--mono)", overflowWrap: "anywhere" }}
              >{`${stage.position} ${stage.name}`}</span>
              <small style={{ color: "var(--muted)" }}>
                {stage.records_in === 0
                  ? "not reached"
                  : `${stage.records_ok} ok · ${stage.records_dropped} dropped · ${stage.records_errored} errored`}
              </small>
            </button>
            {/* a sibling of the row rather than a child, because reading a
                stage's code is not the same as selecting that stage */}
            <button
              type="button"
              onClick={() => onSource(stage.position)}
              aria-label={`source of ${stage.name}`}
              style={{
                background: "none",
                border: 0,
                color: "var(--muted)",
                cursor: "pointer",
                padding: "0.35rem 0.5rem",
                // a long stage name wraps; the icon must not be squeezed away
                flexShrink: 0,
              }}
            >
              <Code size={13} aria-hidden />
            </button>
          </li>
        ))}
      </ul>
      <PaneHeading>fields</PaneHeading>
      {fields.length === 0 && <Empty>no output to measure</Empty>}
      <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {fields.map((stats) => (
          <li key={stats.field}>
            <button
              type="button"
              onClick={() => onField(stats.field === field ? null : stats.field)}
              aria-current={stats.field === field}
              style={rowStyle(stats.field === field)}
            >
              <span style={{ fontFamily: "var(--mono)" }}>{stats.field}</span>
              <small style={{ color: "var(--muted)" }}>
                {stats.inferred_type} · {stats.non_null_count} set
                {stats.null_count > 0 ? ` · ${stats.null_count} null` : ""}
              </small>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}

export function PaneHeading({ children }: { children: string }) {
  return (
    <h2
      style={{
        margin: 0,
        padding: "0.5rem 0.6rem 0.25rem",
        fontSize: "0.7rem",
        textTransform: "uppercase",
        letterSpacing: "0.06em",
        color: "var(--muted)",
      }}
    >
      {children}
    </h2>
  );
}

export function Empty({ children }: { children: string }) {
  return <p style={{ padding: "0.5rem 0.6rem", color: "var(--muted)" }}>{children}</p>;
}

function rowStyle(selected: boolean) {
  return {
    display: "block",
    width: "100%",
    // min-content would otherwise keep a long stage name from yielding to the icon
    minWidth: 0,
    textAlign: "left" as const,
    background: selected ? "var(--surface)" : "none",
    border: 0,
    borderLeft: `2px solid ${selected ? "var(--accent)" : "transparent"}`,
    padding: "0.35rem 0.6rem",
    color: "var(--text)",
    cursor: "pointer",
    font: "inherit",
    fontSize: "0.8rem",
  };
}
