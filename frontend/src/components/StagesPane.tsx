import { Code, FileCode, FileInput, FileOutput } from "lucide-react";
import { useState } from "react";
import type { FieldStats, FileRole, StageSummary } from "../api";
import { Counts } from "./Counts";
import { Splitter } from "./Splitter";
import { Empty, PaneHeading, clamp, outlineButton } from "./shared";

interface Props {
  stages: StageSummary[];
  position: number;
  fields: FieldStats[];
  field: string | null;
  onStage: (position: number) => void;
  onField: (field: string | null) => void;
  onSource: (position: number) => void;
  onFile: (role: FileRole) => void;
}

/** The pipeline in declaration order, and the fields the chosen stage produced. */
export function StagesPane(props: Props) {
  const { stages, position, fields, field, onStage, onField, onSource, onFile } = props;
  // the page header takes roughly the first hundred pixels, so this puts the
  // split between stages and fields about halfway down the window
  const [height, setHeight] = useState(() => clamp(window.innerHeight / 2 - 100));
  return (
    <aside style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
      <div style={{ height, flexShrink: 0, overflowY: "auto" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            paddingRight: "0.5rem",
          }}
        >
          <PaneHeading>stages</PaneHeading>
          <button
            type="button"
            onClick={() => onFile("script")}
            aria-label="script file"
            style={{ ...outlineButton, display: "flex", alignItems: "center", gap: "0.3rem" }}
          >
            <FileCode size={13} aria-hidden />
            script
          </button>
        </div>
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {stages.map((stage) => (
            <li key={stage.position} style={{ display: "flex", alignItems: "flex-start" }}>
              <button
                type="button"
                onClick={() => onStage(stage.position)}
                aria-current={stage.position === position}
                style={rowStyle(stage.position === position)}
              >
                <span
                  style={{ display: "block", fontFamily: "var(--mono)", overflowWrap: "anywhere" }}
                >{`${stage.position} ${stage.name}`}</span>
                <small style={{ display: "block", color: "var(--muted)" }}>
                  {stage.records_in === 0 ? (
                    "not reached"
                  ) : (
                    <Counts
                      ok={stage.records_ok}
                      dropped={stage.records_dropped}
                      errored={stage.records_errored}
                    />
                  )}
                </small>
              </button>
              {/* siblings of the row rather than children, because reading a
                stage's code or file is not the same as selecting that stage */}
              {stage.kind === "source" && (
                <IconButton label="input file" onClick={() => onFile("input")}>
                  <FileInput size={13} aria-hidden />
                </IconButton>
              )}
              {stage.kind === "accumulator" && (
                <IconButton label="output file" onClick={() => onFile("output")}>
                  <FileOutput size={13} aria-hidden />
                </IconButton>
              )}
              <IconButton
                label={`source of ${stage.position} ${stage.name}`}
                onClick={() => onSource(stage.position)}
              >
                <Code size={13} aria-hidden />
              </IconButton>
            </li>
          ))}
        </ul>
      </div>
      <Splitter axis="y" onDrag={(delta) => setHeight((size) => clamp(size + delta))} />
      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", paddingTop: "0.5rem" }}>
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
                <span style={{ display: "block", fontFamily: "var(--mono)" }}>{stats.field}</span>
                <small style={{ display: "block", color: "var(--muted)" }}>
                  {stats.inferred_type} · {stats.non_null_count} set
                  {stats.null_count > 0 ? ` · ${stats.null_count} null` : ""}
                </small>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

function IconButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      style={{
        background: "none",
        border: 0,
        color: "var(--muted)",
        cursor: "pointer",
        // matches the row's top padding, so the icon sits on the name's line
        padding: "0.5rem 0.4rem",
        // a long stage name wraps; the icon must not be squeezed away
        flexShrink: 0,
      }}
    >
      {children}
    </button>
  );
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
    padding: "0.5rem 0.75rem",
    color: "var(--text)",
    cursor: "pointer",
    font: "inherit",
    fontSize: "0.8rem",
  };
}
