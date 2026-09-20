import { Database } from "lucide-react";
import { useEffect, useState } from "react";
import { type Meta, type RunListing, api } from "./api";

// the shell: header, data loading, and the runs list. The screens of
// docs/ui-specification.md land on top of this in the next slice.
export function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [runs, setRuns] = useState<RunListing[] | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.meta(), api.runs()])
      .then(([loadedMeta, page]) => {
        setMeta(loadedMeta);
        setRuns(page.items);
      })
      .catch((error: Error) => setFailure(error.message));
  }, []);

  return (
    <>
      <header className="app-header">
        <h1>squeegee</h1>
        <span className="mono" style={{ color: "var(--muted)", fontSize: "0.8rem" }}>
          <Database size={12} aria-hidden /> {meta?.database_path ?? "connecting"}
        </span>
      </header>
      <main>
        {failure && <p className="status-error">{failure}</p>}
        {runs && <RunsTable runs={runs} />}
      </main>
    </>
  );
}

function RunsTable({ runs }: { runs: RunListing[] }) {
  if (runs.length === 0) return <p style={{ color: "var(--muted)" }}>No runs recorded yet.</p>;
  return (
    <table style={{ borderCollapse: "collapse", width: "100%" }}>
      <thead>
        <tr style={{ textAlign: "left", color: "var(--muted)" }}>
          <th>run</th>
          <th>script</th>
          <th>status</th>
          <th>in</th>
          <th>out</th>
          <th>dropped</th>
          <th>errored</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((run) => (
          <tr key={run.run_id} style={{ borderTop: "1px solid var(--border)" }}>
            <td className="mono">{run.run_id}</td>
            <td className="mono">{run.script_path.split("/").pop()}</td>
            <td className={run.status === "failed" ? "status-error" : "status-ok"}>{run.status}</td>
            <td className="mono">{run.records_in}</td>
            <td className="mono">{run.records_out}</td>
            <td className="mono">{run.records_dropped}</td>
            <td className="mono">{run.records_errored}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
