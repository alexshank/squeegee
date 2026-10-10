import { type FileRole, api } from "../api";
import { useApi } from "../useApi";
import { Modal } from "./Modal";
import { RawValue } from "./RawValue";
import { StageSource } from "./StageSource";

interface Props {
  runId: number;
  role: FileRole;
  onClose: () => void;
}

/** A file the run kept: the script that ran, the input it read, or the output it wrote. */
export function FileModal({ runId, role, onClose }: Props) {
  const file = useApi(() => api.file(runId, role), [runId, role]);

  return (
    <Modal label={`${role} file`} onClose={onClose}>
      {file.loading && <p style={{ color: "var(--muted)" }}>loading…</p>}
      {file.error && <p className="status-error">{file.error}</p>}
      {file.data &&
        (role === "script" ? (
          <StageSource source={file.data.content} name={file.data.path} />
        ) : (
          <>
            {/* the path stays out of the label, which is uppercased */}
            <p style={{ margin: "0 0 0.4rem", fontFamily: "var(--mono)", fontSize: "0.75rem" }}>
              {file.data.path}
            </p>
            <RawValue
              label={role}
              value={file.data.content}
              format={file.data.format}
              maxHeight="65vh"
            />
          </>
        ))}
    </Modal>
  );
}
