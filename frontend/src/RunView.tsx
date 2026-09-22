import { AlertTriangle } from "lucide-react";
import { useRef } from "react";
import { api } from "./api";
import { FieldPanel } from "./components/FieldPanel";
import { RecordIoPane } from "./components/RecordIoPane";
import { RecordsPane } from "./components/RecordsPane";
import { SourceModal } from "./components/SourceModal";
import { StagesPane } from "./components/StagesPane";
import { TracePane } from "./components/TracePane";
import { integerParam, statusParam } from "./params";
import { back, useParamSetter } from "./router";
import { useApi } from "./useApi";
import { useRecords } from "./useRecords";

interface Props {
  runId: number;
  params: URLSearchParams;
}

/** Anything that failed to load, rather than a pane that quietly shows nothing. */
function Problems({ problems }: { problems: (string | null)[] }) {
  const failures = problems.filter((problem): problem is string => problem !== null);
  if (failures.length === 0) return null;
  return (
    <ul style={{ margin: "0.5rem 0 0", paddingLeft: "1.1rem" }} className="status-error">
      {failures.map((failure) => (
        <li key={failure}>{failure}</li>
      ))}
    </ul>
  );
}

/** The split view: stages, the records of one stage, and one record's trace. */
export function RunView({ runId, params }: Props) {
  const setParams = useParamSetter();
  const position = integerParam(params, "stage") ?? 0;
  // the record table filters on what a stage did to a record; stepping through
  // the trace filters on where a record ended up. Two questions, two parameters.
  const status = statusParam(params, "status");
  const step = statusParam(params, "step");
  const search = params.get("q") ?? "";
  const field = params.get("field");
  const recordIndex = integerParam(params, "record");
  const sourcePosition = integerParam(params, "source");

  const run = useApi(() => api.run(runId), [runId]);
  const fields = useApi(() => api.fields(runId, position), [runId, position]);
  const records = useRecords(runId, position, status, search);
  const trace = useApi(
    () =>
      recordIndex === null
        ? Promise.resolve(null)
        : api.trace(runId, recordIndex, step ? { status: step } : {}),
    [runId, recordIndex, step],
  );
  const fieldDetail = useApi(
    () => (field === null ? Promise.resolve(null) : api.field(runId, position, field)),
    [runId, position, field],
  );

  const failure = run.data?.failure ?? null;
  // useApi keeps the last good value visible while the next one loads, so both
  // panes must ignore a trace that is still the record selected before this one
  const current = trace.data?.record_index === recordIndex ? trace.data : null;
  // closing walks the history back when opening pushed onto it, so a shared
  // link that arrives with the modal open does not gain an entry to walk
  const pushedSource = useRef(false);

  function openSource(next: number) {
    pushedSource.current = true;
    setParams({ source: String(next) });
  }

  function closeSource() {
    // replacing instead would leave an entry identical to the one before it,
    // and Back would look broken
    if (pushedSource.current) {
      pushedSource.current = false;
      back();
    } else {
      setParams({ source: null }, true);
    }
  }

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
        <Problems problems={[run.error, fields.error, fieldDetail.error]} />
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
          onSource={(next) => openSource(next)}
        />
        <div style={{ display: "flex", flexDirection: "column", minWidth: 0, overflowY: "auto" }}>
          <RecordsPane
            records={records.items}
            hasMore={records.hasMore}
            loading={records.loading}
            error={records.error}
            status={status}
            search={search}
            recordIndex={recordIndex}
            onStatus={(next) => setParams({ status: next })}
            onSearch={(next) => setParams({ q: next || null }, true)}
            onRecord={(index) => setParams({ record: String(index) })}
            onLoadMore={records.loadMore}
          />
          <RecordIoPane
            trace={current}
            error={trace.error}
            position={position}
            recordIndex={recordIndex}
            onSource={(next) => openSource(next)}
          />
          {fieldDetail.data && <FieldPanel detail={fieldDetail.data} />}
        </div>
        <TracePane
          trace={current}
          loading={trace.loading}
          error={trace.error}
          step={step}
          onStep={(next) => setParams({ step: next })}
          onRecord={(index) => setParams({ record: String(index) })}
        />
      </div>
      {sourcePosition !== null && (
        <SourceModal runId={runId} position={sourcePosition} onClose={closeSource} />
      )}
    </>
  );
}
