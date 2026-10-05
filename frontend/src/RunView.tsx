import { AlertTriangle } from "lucide-react";
import { useRef, useState } from "react";
import { type FileRole, type Status, api } from "./api";
import { Counts } from "./components/Counts";
import { FieldPanel } from "./components/FieldPanel";
import { FileModal } from "./components/FileModal";
import { RecordIoPane } from "./components/RecordIoPane";
import { RecordsPane } from "./components/RecordsPane";
import { SourceModal } from "./components/SourceModal";
import { Splitter } from "./components/Splitter";
import { StagesPane } from "./components/StagesPane";
import { TracePane } from "./components/TracePane";
import { fileParam, integerParam, statusParam } from "./params";
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
  const status = statusParam(params, "status");
  const search = params.get("q") ?? "";
  const field = params.get("field");
  const recordIndex = integerParam(params, "record");
  const sourcePosition = integerParam(params, "source");
  const fileRole = fileParam(params);

  const run = useApi(() => api.run(runId), [runId]);
  const fields = useApi(() => api.fields(runId, position), [runId, position]);
  const records = useRecords(runId, position, status, search);
  const trace = useApi(
    () =>
      recordIndex === null
        ? Promise.resolve(null)
        : // stepping walks the records table, so it carries the table's filters
          api.trace(runId, recordIndex, {
            stage: position,
            status: status ?? undefined,
            q: search || undefined,
          }),
    [runId, recordIndex, position, status, search],
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
  const pushedModal = useRef(false);
  const [left, setLeft] = useState(300);
  const [right, setRight] = useState(420);
  const [bottom, setBottom] = useState(320);
  // no pane may be dragged shut, or its handle would be lost with it
  const clamp = (size: number) => Math.max(120, size);

  // a stage's source and a run's files share one modal slot, so opening either closes the other
  function openModal(updates: { source: string | null; file: FileRole | null }) {
    pushedModal.current = true;
    setParams(updates);
  }

  // the filter applies at once; the record follows once the server says whether
  // the filtered table still lists it, so typing is never held up by a request.
  // the trace asked for here is the one useApi is also loading; sharing it would
  // mean an effect that also fires on deep links and stage changes, where
  // "never reached this stage" is the right answer rather than a jump
  async function refilter(nextStatus: Status | null, nextSearch: string, replace: boolean) {
    setParams({ status: nextStatus, q: nextSearch || null }, replace);
    if (recordIndex === null) return;
    const asked = window.location.search;
    const filters = { status: nextStatus ?? undefined, q: nextSearch || undefined };
    try {
      const [mine, first] = await Promise.all([
        api.trace(runId, recordIndex, { stage: position, ...filters }),
        api.stageRecords(runId, position, { ...filters, limit: 1 }),
      ]);
      // any newer filter, record or stage changes the URL and makes this answer stale
      if (window.location.search !== asked || mine.listed) return;
      const index = first.items[0]?.record_index;
      setParams({ record: index === undefined ? null : String(index) }, true);
    } catch {
      // the table and the trace each report their own load failure
    }
  }

  function closeModal() {
    // replacing instead would leave an entry identical to the one before it,
    // and Back would look broken
    if (pushedModal.current) {
      pushedModal.current = false;
      back();
    } else {
      setParams({ source: null, file: null }, true);
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
            {run.data ? (
              <>
                {`${run.data.records_in} in · `}
                <Counts
                  ok={run.data.records_out}
                  dropped={run.data.records_dropped}
                  errored={run.data.records_errored}
                  okLabel="out"
                />
              </>
            ) : (
              "loading"
            )}
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
          gridTemplateColumns: `${left}px auto minmax(0, 1fr) auto ${right}px`,
          height: "calc(100vh - 5.5rem)",
        }}
      >
        <StagesPane
          stages={run.data?.stages ?? []}
          position={position}
          fields={fields.data?.items ?? []}
          field={field}
          onStage={(next) => setParams({ stage: String(next), field: null })}
          onField={(next) => setParams({ field: next })}
          onSource={(next) => openModal({ source: String(next), file: null })}
          onFile={(role) => openModal({ source: null, file: role })}
        />
        <Splitter axis="x" onDrag={(delta) => setLeft((size) => clamp(size + delta))} />
        <div style={{ display: "flex", flexDirection: "column", minWidth: 0, minHeight: 0 }}>
          <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
            <RecordsPane
              records={records.items}
              hasMore={records.hasMore}
              loading={records.loading}
              error={records.error}
              status={status}
              search={search}
              recordIndex={recordIndex}
              onStatus={(next) => void refilter(next, search, false)}
              onSearch={(next) => void refilter(status, next, true)}
              onRecord={(index) => setParams({ record: String(index) })}
              onLoadMore={records.loadMore}
            />
          </div>
          <Splitter axis="y" onDrag={(delta) => setBottom((size) => clamp(size - delta))} />
          <div style={{ height: bottom, flexShrink: 0, overflowY: "auto" }}>
            <RecordIoPane
              trace={current}
              error={trace.error}
              position={position}
              recordIndex={recordIndex}
              onSource={(next) => openModal({ source: String(next), file: null })}
            />
            {fieldDetail.data && <FieldPanel detail={fieldDetail.data} />}
          </div>
        </div>
        <Splitter axis="x" onDrag={(delta) => setRight((size) => clamp(size - delta))} />
        <TracePane
          trace={current}
          loading={trace.loading}
          error={trace.error}
          onRecord={(index) => setParams({ record: String(index) })}
        />
      </div>
      {sourcePosition !== null && (
        <SourceModal runId={runId} position={sourcePosition} onClose={closeModal} />
      )}
      {fileRole !== null && <FileModal runId={runId} role={fileRole} onClose={closeModal} />}
    </>
  );
}
