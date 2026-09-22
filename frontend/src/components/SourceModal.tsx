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
  const pressedBackdrop = useRef(false);

  // showModal rather than the open attribute, for the focus trap and Escape
  useEffect(() => {
    const opener = document.activeElement;
    dialog.current?.showModal();
    return () => {
      dialog.current?.close();
      // the icon that opened this is where the keyboard was, so send it back
      if (opener instanceof HTMLElement) opener.focus();
    };
  }, []);

  return (
    // biome-ignore lint/a11y/useKeyWithClickEvents: Escape and the close button are the keyboard paths; this handler only adds click-outside
    <dialog
      ref={dialog}
      aria-label={`source of stage ${position}`}
      onCancel={onClose}
      // the press decides, not the click: a selection dragged out of the source
      // reports the dialog as the click target, and so does its own scrollbar
      onMouseDown={(pressed) => {
        pressedBackdrop.current = outside(pressed, dialog.current);
      }}
      onClick={(clicked) =>
        pressedBackdrop.current && outside(clicked, dialog.current) && onClose()
      }
      style={{
        width: "min(60rem, 90vw)",
        maxHeight: "80vh",
        background: "var(--bg)",
        color: "var(--text)",
        border: "1px solid var(--border)",
        // no padding on the dialog itself: padding is part of its box, so a
        // click on it would read as a click outside and close the modal
        padding: 0,
      }}
    >
      <div style={{ padding: "0.75rem" }}>
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
      </div>
    </dialog>
  );
}

/** True for a pointer event on the backdrop, rather than on the dialog or its scrollbar. */
function outside(event: React.MouseEvent, dialog: HTMLDialogElement | null): boolean {
  if (dialog === null || event.target !== dialog) return false;
  const box = dialog.getBoundingClientRect();
  return (
    event.clientX < box.left ||
    event.clientX > box.right ||
    event.clientY < box.top ||
    event.clientY > box.bottom
  );
}
