// the client for the read-only API, typed against docs/api.md

export type Status = "ok" | "dropped" | "error";
export type RunStatus = "started" | "finished" | "failed" | "aborted";

export interface Page<Item> {
  items: Item[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface Meta {
  squeegee_version: string;
  database_path: string;
  run_count: number;
}

export interface RunListing {
  run_id: number;
  script_path: string;
  input_path: string;
  output_path: string | null;
  started_at: string;
  ended_at: string | null;
  duration_us: number | null;
  status: RunStatus;
  stage_count: number;
  records_in: number;
  records_out: number;
  records_dropped: number;
  records_errored: number;
}

export interface Failure {
  stage_position: number;
  stage_name: string;
  record_index: number;
  error_type: string;
  error_message: string;
}

export interface StageSummary {
  position: number;
  name: string;
  description: string | null;
  records_in: number;
  records_ok: number;
  records_dropped: number;
  records_errored: number;
  duration_us_total: number;
  duration_us_median: number | null;
  duration_us_p95: number | null;
}

export interface Run extends RunListing {
  script_sha256: string;
  squeegee_version: string;
  python_version: string;
  options: Record<string, unknown>;
  stages: StageSummary[];
  failure: Failure | null;
}

export interface StageDetail extends StageSummary {
  stage_version_id: number;
  input_type: string | null;
  output_type: string | null;
  source_text: string;
  source_sha256: string;
  source_language: string;
  first_seen_at: string;
  also_used_by_runs: number[];
}

export type Record_ = Record<string, unknown>;

export interface RecordEvent {
  record_index: number;
  status: Status;
  input: Record_;
  output: Record_ | null;
  error_type: string | null;
  error_message: string | null;
  duration_us: number;
}

export interface TraceEvent extends Omit<RecordEvent, "record_index"> {
  position: number;
  stage_name: string;
  changed_fields: string[];
}

export interface Trace {
  record_index: number;
  source: Record_;
  final_status: Status | null;
  events: TraceEvent[];
  previous_record_index: number | null;
  next_record_index: number | null;
}

export interface FieldStats {
  field: string;
  inferred_type: string;
  non_null_count: number;
  null_count: number;
  distinct_count: number;
  min: number | null;
  max: number | null;
  mean: number | null;
  median: number | null;
  sum: number | null;
}

export interface Distribution {
  stats: FieldStats;
  histogram: { lower: number; upper: number; count: number }[] | null;
  top_values: { value: unknown; count: number }[] | null;
}

export interface FieldDetail {
  field: string;
  inferred_type: string;
  after: Distribution;
  before: Distribution | null;
}

export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly parameter: string | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function get<Result>(path: string, params: Record<string, unknown> = {}): Promise<Result> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) query.set(key, String(value));
  }
  const suffix = query.size > 0 ? `?${query}` : "";
  const response = await fetch(`/api${path}${suffix}`);
  const body = await response.json();
  if (!response.ok) {
    const error = body.error ?? { code: "unknown", message: response.statusText, parameter: null };
    throw new ApiError(error.code, error.message, error.parameter);
  }
  return body as Result;
}

export const api = {
  meta: () => get<Meta>("/meta"),
  runs: (params: { limit?: number; cursor?: string; script?: string } = {}) =>
    get<Page<RunListing>>("/runs", params),
  run: (runId: number) => get<Run>(`/runs/${runId}`),
  stages: (runId: number) => get<{ items: StageSummary[] }>(`/runs/${runId}/stages`),
  stage: (runId: number, position: number) => get<StageDetail>(`/runs/${runId}/stages/${position}`),
  stageRecords: (
    runId: number,
    position: number,
    params: { status?: Status; q?: string; limit?: number; cursor?: string } = {},
  ) => get<Page<RecordEvent>>(`/runs/${runId}/stages/${position}/records`, params),
  trace: (runId: number, recordIndex: number, params: { status?: Status } = {}) =>
    get<Trace>(`/runs/${runId}/records/${recordIndex}`, params),
  fields: (runId: number, position: number) =>
    get<{ records_considered: number; items: FieldStats[] }>(
      `/runs/${runId}/stages/${position}/fields`,
    ),
  field: (
    runId: number,
    position: number,
    field: string,
    params: { bins?: number; top?: number } = {},
  ) =>
    get<FieldDetail>(
      `/runs/${runId}/stages/${position}/fields/${encodeURIComponent(field)}`,
      params,
    ),
};
