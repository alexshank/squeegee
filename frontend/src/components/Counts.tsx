interface Props {
  ok: number;
  dropped: number;
  errored: number;
  // a run's survivors are "out", a stage's are "ok"
  okLabel?: string;
}

/** Outcome counts in their status colours, with zeros muted so real problems stand out. */
export function Counts({ ok, dropped, errored, okLabel = "ok" }: Props) {
  const parts = [
    [ok, okLabel, "status-ok"],
    [dropped, "dropped", "status-dropped"],
    [errored, "errored", "status-error"],
  ] as const;
  return (
    <span>
      {parts.map(([count, word, className], index) => (
        <span key={word}>
          {index > 0 && <span style={{ color: "var(--muted)" }}> · </span>}
          <span
            className={count > 0 ? className : undefined}
            style={count > 0 ? {} : { color: "var(--muted)" }}
          >
            {count} {word}
          </span>
        </span>
      ))}
    </span>
  );
}
