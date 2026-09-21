import type { Distribution, FieldDetail } from "../api";

/** Field analytics: the distribution after the stage, and before it where it existed. */
export function FieldPanel({ detail }: { detail: FieldDetail }) {
  return (
    <section style={{ borderTop: "1px solid var(--border)", padding: "0.5rem 0" }}>
      <h3 style={{ margin: "0 0 0.4rem", fontSize: "0.85rem", fontFamily: "var(--mono)" }}>
        {detail.field} <span style={{ color: "var(--muted)" }}>· {detail.inferred_type}</span>
      </h3>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
        <Side title="after this stage" distribution={detail.after} />
        {detail.before ? (
          <Side title="before this stage" distribution={detail.before} />
        ) : (
          <p style={{ color: "var(--muted)", fontSize: "0.75rem" }}>
            This stage created the field; there is nothing to compare against.
          </p>
        )}
      </div>
    </section>
  );
}

function Side({ title, distribution }: { title: string; distribution: Distribution }) {
  const { stats, histogram, top_values } = distribution;
  return (
    <div>
      <div style={{ fontSize: "0.7rem", textTransform: "uppercase", color: "var(--muted)" }}>
        {title}
      </div>
      {histogram && <Histogram buckets={histogram} />}
      <dl
        style={{
          display: "grid",
          gridTemplateColumns: "auto 1fr",
          gap: "0 0.5rem",
          margin: "0.4rem 0 0",
          fontSize: "0.75rem",
        }}
      >
        <Figure name="set" value={stats.non_null_count} />
        <Figure name="null" value={stats.null_count} />
        <Figure name="distinct" value={stats.distinct_count} />
        {stats.mean !== null && <Figure name="mean" value={round(stats.mean)} />}
        {stats.median !== null && <Figure name="median" value={round(stats.median)} />}
        {stats.sum !== null && <Figure name="sum" value={round(stats.sum)} />}
        {stats.min !== null && <Figure name="min" value={round(stats.min)} />}
        {stats.max !== null && <Figure name="max" value={round(stats.max)} />}
      </dl>
      {top_values && (
        <ul style={{ listStyle: "none", margin: "0.4rem 0 0", padding: 0, fontSize: "0.75rem" }}>
          {top_values.slice(0, 5).map((entry) => (
            <li key={String(entry.value)} style={{ fontFamily: "var(--mono)" }}>
              {String(entry.value)} <span style={{ color: "var(--muted)" }}>× {entry.count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Histogram({ buckets }: { buckets: { lower: number; upper: number; count: number }[] }) {
  const tallest = Math.max(...buckets.map((bucket) => bucket.count), 1);
  return (
    <div
      style={{ display: "flex", alignItems: "flex-end", gap: "1px", height: "3.5rem" }}
      role="img"
      aria-label={`histogram of ${buckets.length} buckets`}
    >
      {buckets.map((bucket) => (
        <div
          key={bucket.lower}
          title={`${round(bucket.lower)}–${round(bucket.upper)}: ${bucket.count}`}
          style={{
            flex: 1,
            height: `${(bucket.count / tallest) * 100}%`,
            minHeight: bucket.count > 0 ? "2px" : "0",
            background: "var(--accent)",
            opacity: 0.7,
          }}
        />
      ))}
    </div>
  );
}

function Figure({ name, value }: { name: string; value: number }) {
  return (
    <>
      <dt style={{ color: "var(--muted)" }}>{name}</dt>
      <dd style={{ margin: 0, fontFamily: "var(--mono)" }}>{value}</dd>
    </>
  );
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}
