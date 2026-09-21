import type { Status } from "../api";

// status is never carried by colour alone: each one has its own glyph
const GLYPHS: Record<Status, string> = { ok: "●", dropped: "–", error: "✕" };

export function StatusPill({ status }: { status: Status }) {
  return (
    <span
      className={`status-${status}`}
      style={{
        fontFamily: "var(--mono)",
        fontSize: "0.75rem",
        border: "1px solid currentColor",
        borderRadius: "999px",
        padding: "0 0.4rem",
        whiteSpace: "nowrap",
      }}
    >
      {GLYPHS[status]} {status}
    </span>
  );
}
