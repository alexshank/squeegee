import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { api } from "../api";
import { useApi } from "../useApi";
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
  const dialog = useRef<HTMLDialogElement>(null);

  // showModal rather than the open attribute, for the focus trap and Escape;
  // optional because jsdom does not implement it and the tests still render
  useEffect(() => dialog.current?.showModal?.(), []);

  return (
    // biome-ignore lint/a11y/useKeyWithClickEvents: Escape and the close button are the keyboard paths; this handler only adds click-outside
    <dialog
      ref={dialog}
      aria-label={`source of stage ${position}`}
      onCancel={onClose}
      onClick={(clicked) => clicked.target === dialog.current && onClose()}
      style={{
        width: "min(60rem, 90vw)",
        maxHeight: "80vh",
        background: "var(--bg)",
        color: "var(--text)",
        border: "1px solid var(--border)",
        padding: "0.75rem",
      }}
    >
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button
          type="button"
          onClick={onClose}
          aria-label="close source"
          style={{
            background: "none",
            border: "1px solid var(--border)",
            color: "var(--muted)",
            cursor: "pointer",
            font: "inherit",
            padding: "0.1rem 0.3rem",
          }}
        >
          <X size={12} aria-hidden />
        </button>
      </div>
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
    </dialog>
  );
}
