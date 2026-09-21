import type { RunListing } from "./api";
import { navigate } from "./router";

const COLUMNS = ["run", "script", "status", "in", "out", "dropped", "errored", "started"];

/** The landing screen: every recorded run, newest first. */
export function RunsList({ runs }: { runs: RunListing[] }) {
  if (runs.length === 0) {
    return <p style={{ color: "var(--muted)" }}>No runs recorded yet.</p>;
  }
  return (
    <table style={{ borderCollapse: "collapse", width: "100%", fontSize: "0.85rem" }}>
      <thead>
        <tr style={{ textAlign: "left", color: "var(--muted)", fontSize: "0.7rem" }}>
          {COLUMNS.map((column) => (
            <th key={column} style={{ padding: "0.3rem" }}>
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {runs.map((run) => (
          <tr
            key={run.run_id}
            tabIndex={0}
            onClick={() => navigate(`/runs/${run.run_id}`)}
            onKeyDown={(event) => activate(event, () => navigate(`/runs/${run.run_id}`))}
            style={{ borderTop: "1px solid var(--border)", cursor: "pointer" }}
          >
            <td style={cell}>{run.run_id}</td>
            <td style={cell}>{run.script_path.split("/").pop()}</td>
            <td style={{ padding: "0.3rem" }}>
              <span className={run.status === "failed" ? "status-error" : "status-ok"}>
                {run.status}
              </span>
            </td>
            <td style={cell}>{run.records_in}</td>
            <td style={cell}>{run.records_out}</td>
            <td style={cell}>{run.records_dropped}</td>
            <td style={cell}>{run.records_errored}</td>
            <td style={{ ...cell, color: "var(--muted)" }}>{run.started_at.slice(0, 19)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const cell = { padding: "0.3rem", fontFamily: "var(--mono)" } as const;

/** A row is only clickable if it is also reachable from the keyboard. */
export function activate(event: React.KeyboardEvent, action: () => void): void {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    action();
  }
}
