// small pieces every pane uses, so headings, labels and buttons look the same everywhere

export const outlineButton = {
  background: "none",
  border: "1px solid var(--border)",
  color: "var(--text)",
  cursor: "pointer",
  font: "inherit",
  fontSize: "0.75rem",
  padding: "0.1rem 0.5rem",
};

export function PaneHeading({ children }: { children: string }) {
  return (
    <h2
      style={{
        margin: 0,
        padding: "0.5rem 0.6rem 0.25rem",
        fontSize: "0.75rem",
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

export function Label({ children }: { children: string }) {
  return (
    <div
      style={{
        fontSize: "0.7rem",
        textTransform: "uppercase",
        letterSpacing: "0.06em",
        color: "var(--muted)",
      }}
    >
      {children}
    </div>
  );
}
