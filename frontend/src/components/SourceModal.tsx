import { api } from "../api";
import { useApi } from "../useApi";
import { Modal } from "./Modal";
import { StageSource } from "./StageSource";

interface Props {
  runId: number;
  position: number;
  onClose: () => void;
}

/** One stage's source, over the page, for any stage rather than the selected one. */
export function SourceModal({ runId, position, onClose }: Props) {
  // fetched here rather than passed in, so the icon of a stage that is not
  // selected can show its source without moving the selection
  const stage = useApi(() => api.stage(runId, position), [runId, position]);

  return (
    <Modal label={`source of stage ${position}`} onClose={onClose}>
      {stage.loading && <p style={{ color: "var(--muted)" }}>loading…</p>}
      {stage.error && <p className="status-error">{stage.error}</p>}
      {stage.data && (
        <>
          <StageSource
            source={stage.data.source_text}
            name={stage.data.name}
            sha={stage.data.source_sha256}
          />
          <p style={{ color: "var(--muted)", fontSize: "0.75rem", marginBottom: 0 }}>
            {stage.data.input_type ?? "unannotated"} → {stage.data.output_type ?? "unannotated"}
            {stage.data.also_used_by_runs.length > 0 &&
              ` · unchanged since runs ${stage.data.also_used_by_runs.join(", ")}`}
          </p>
        </>
      )}
    </Modal>
  );
}
