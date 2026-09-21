import { Database } from "lucide-react";
import { RunView } from "./RunView";
import { RunsList } from "./RunsList";
import { type RunListing, api } from "./api";
import { navigate, useLocation } from "./router";
import { useApi } from "./useApi";

export function App() {
  const location = useLocation();
  const meta = useApi(() => api.meta(), []);
  const runId = matchRun(location.path);

  return (
    <>
      <header className="app-header">
        <h1>
          <button type="button" onClick={() => navigate("/")} style={homeStyle}>
            squeegee
          </button>
        </h1>
        <span className="mono" style={{ color: "var(--muted)", fontSize: "0.75rem" }}>
          <Database size={11} aria-hidden /> {meta.data?.database_path ?? "connecting"}
        </span>
      </header>
      {runId === null ? <RunsScreen /> : <RunView runId={runId} params={location.params} />}
    </>
  );
}

function RunsScreen() {
  const runs = useApi(() => api.runs(), []);
  return (
    <main>
      {runs.error && <p className="status-error">{runs.error}</p>}
      {runs.data && <RunsList runs={runs.data.items as RunListing[]} />}
    </main>
  );
}

function matchRun(path: string): number | null {
  const match = /^\/runs\/(\d+)$/.exec(path);
  return match?.[1] ? Number(match[1]) : null;
}

const homeStyle = {
  background: "none",
  border: 0,
  padding: 0,
  color: "inherit",
  cursor: "pointer",
  font: "inherit",
} as const;
