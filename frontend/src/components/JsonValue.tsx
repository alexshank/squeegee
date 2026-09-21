import { useState } from "react";

interface Props {
  value: unknown;
  changed?: string[];
}

/** A record rendered as keys and values, with the changed keys marked. */
export function JsonValue({ value, changed = [] }: Props) {
  if (value === null || typeof value !== "object") {
    return <span style={{ fontFamily: "var(--mono)" }}>{format(value)}</span>;
  }
  const entries = Object.entries(value as Record<string, unknown>);
  return (
    <dl style={{ margin: 0, display: "grid", gridTemplateColumns: "auto 1fr", gap: "0 0.5rem" }}>
      {entries.map(([key, entry]) => (
        <Entry key={key} name={key} value={entry} changed={changed.includes(key)} />
      ))}
    </dl>
  );
}

function Entry({ name, value, changed }: { name: string; value: unknown; changed: boolean }) {
  const [open, setOpen] = useState(false);
  const nested = value !== null && typeof value === "object";
  return (
    <>
      <dt
        style={{
          fontFamily: "var(--mono)",
          fontSize: "0.8rem",
          color: changed ? "var(--text)" : "var(--muted)",
          fontWeight: changed ? 600 : 400,
          textDecoration: changed ? "underline" : "none",
        }}
      >
        {name}
      </dt>
      <dd style={{ margin: 0, fontFamily: "var(--mono)", fontSize: "0.8rem" }}>
        {nested ? (
          <button
            type="button"
            onClick={() => setOpen(!open)}
            style={{
              background: "none",
              border: 0,
              padding: 0,
              color: "var(--accent)",
              cursor: "pointer",
              font: "inherit",
            }}
          >
            {open ? "▾ " : "▸ "}
            {open ? JSON.stringify(value, null, 1) : summarize(value)}
          </button>
        ) : (
          format(value)
        )}
      </dd>
    </>
  );
}

function summarize(value: unknown): string {
  return Array.isArray(value) ? `[${value.length} items]` : "{…}";
}

function format(value: unknown): string {
  if (value === null) return "null";
  if (value === undefined) return "—";
  return typeof value === "string" ? value : JSON.stringify(value);
}
