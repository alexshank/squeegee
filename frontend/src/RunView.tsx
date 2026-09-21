import { AlertTriangle } from "lucide-react";
import type { Status } from "./api";
import { api } from "./api";
import { FieldPanel } from "./components/FieldPanel";
import { RecordsPane } from "./components/RecordsPane";
import { StagesPane } from "./components/StagesPane";
import { TracePane } from "./components/TracePane";
import { useParamSetter } from "./router";
import { useApi } from "./useApi";

interface Props {
  runId: number;
  params: URLSearchParams;
}

/** The split view: stages, the records of one stage, and one record's trace. */
export function RunView({ runId, params }: Props) {
  const setParams = useParamSetter();
  const position = Number(params.get("stage") ?? 0);
  const status = (params.get("status") as Status | null) ?? null;
  const search = params.get("q") ?? "";
  const field = params.get("field");
  const recordParam = params.get("record");
  const recordIndex = recordParam === null ? null : Number(recordParam);

  const run = useApi(() => api.run(runId), [runId]);
  const stage = useApi(() => api.stage(runId, position), [runId, position]);
  const fields = useApi(() => api.fields(runId, position), [runId, position]);
  const records = useApi(
    () =>
      api.stageRecords(runId, position, {
        ...(status ? { status } : {}),
        ...(search ? { q: search } : {}),
      }),
    [runId, position, status, search],
  );
  const trace = useApi(
    () =>
      recordIndex === null
        ? Promise.resolve(null)
        : api.trace(runId, recordIndex, status ? { status } : {}),
    [runId, recordIndex, status],
  );
  const fieldDetail = useApi(
    () => (field === null ? Promise.resolve(null) : api.field(runId, position, field)),
    [runId, position, field],
  );

  const failure = run.data?.failure ?? null;

  return (
    <>
      <div style={{ padding: "0.6rem 0.75rem", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", alignItems: "baseline" }}>
          <strong style={{ fontFamily: "var(--mono)" }}>
            run {runId} · {run.data?.script_path.split("/").pop() ?? "…"}
          </strong>
          <span style={{ color: "var(--muted)", fontSize: "0.8rem" }}>
            {run.data
              ? `${run.data.records_in} in · ${run.data.records_out} out · ${run.data.records_dropped} dropped · ${run.data.records_errored} errored`
              : "loading"}
          </span>
        </div>
        {failure && (
          <p
            className="status-error"
            style={{
              margin: "0.5rem 0 0",
              border: "1px solid currentColor",
              padding: "0.4rem 0.6rem",
              fontSize: "0.82rem",
            }}
          >
            <AlertTriangle size={13} aria-hidden /> failed at stage {failure.stage_position} (
            {failure.stage_name}), record {failure.record_index}:{" "}
            <span style={{ fontFamily: "var(--mono)" }}>
              {failure.error_type}: {failure.error_message}
            </span>{" "}
            <button
              type="button"
              onClick={() =>
                setParams({
                  stage: String(failure.stage_position),
                  record: String(failure.record_index),
                })
              }
              style={{
                background: "none",
                border: "1px solid currentColor",
                color: "inherit",
                cursor: "pointer",
                font: "inherit",
                fontSize: "0.75rem",
              }}
            >
              show it
            </button>
          </p>
        )}
        {run.error && <p className="status-error">{run.error}</p>}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "14rem minmax(0, 1fr) 22rem",
          height: "calc(100vh - 7rem)",
        }}
      >
        <StagesPane
          stages={run.data?.stages ?? []}
          position={position}
          fields={fields.data?.items ?? []}
          field={field}
          onStage={(next) => setParams({ stage: String(next), field: null })}
          onField={(next) => setParams({ field: next })}
        />
        <div style={{ display: "flex", flexDirection: "column", minWidth: 0, overflowY: "auto" }}>
          <RecordsPane
            stage={stage.data}
            page={records.data}
            status={status}
            search={search}
            recordIndex={recordIndex}
            onStatus={(next) => setParams({ status: next })}
            onSearch={(next) => setParams({ q: next || null })}
            onRecord={(index) => setParams({ record: String(index) })}
          />
          {fieldDetail.data && <FieldPanel detail={fieldDetail.data} />}
        </div>
        <TracePane
          trace={trace.data}
          status={status}
          onRecord={(index) => setParams({ record: String(index) })}
        />
      </div>
    </>
  );
}
