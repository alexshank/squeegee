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
  // callers render this inside muted text, so zeros and separators stay muted
  return (
    <>
      {parts.map(([count, word, className], index) => (
        <span key={word}>
          {index > 0 && " · "}
          <span className={count > 0 ? className : undefined}>
            {count} {word}
          </span>
        </span>
      ))}
    </>
  );
}
