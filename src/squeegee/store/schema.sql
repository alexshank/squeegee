-- the schema of docs/data-model.md; every table is append-only, enforced by triggers

CREATE TABLE IF NOT EXISTS runs (
    id                INTEGER PRIMARY KEY,
    started_at        TEXT    NOT NULL,
    script_path       TEXT    NOT NULL,
    script_sha256     TEXT    NOT NULL,
    input_path        TEXT    NOT NULL,
    output_path       TEXT,
    squeegee_version  TEXT    NOT NULL,
    python_version    TEXT    NOT NULL,
    options_json      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS run_events (
    id          INTEGER PRIMARY KEY,
    run_id      INTEGER NOT NULL REFERENCES runs(id),
    at          TEXT    NOT NULL,
    kind        TEXT    NOT NULL CHECK (kind IN ('started', 'finished', 'failed', 'aborted')),
    detail_json TEXT
);

CREATE TABLE IF NOT EXISTS stage_versions (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    source_text   TEXT NOT NULL,
    description   TEXT,
    input_type    TEXT,
    output_type   TEXT,
    first_seen_at TEXT NOT NULL,
    UNIQUE (name, source_sha256)
);

CREATE TABLE IF NOT EXISTS run_stages (
    id                INTEGER PRIMARY KEY,
    run_id            INTEGER NOT NULL REFERENCES runs(id),
    stage_version_id  INTEGER NOT NULL REFERENCES stage_versions(id),
    position          INTEGER NOT NULL,
    UNIQUE (run_id, position)
);

CREATE TABLE IF NOT EXISTS records (
    id           INTEGER PRIMARY KEY,
    run_id       INTEGER NOT NULL REFERENCES runs(id),
    record_index INTEGER NOT NULL,
    source_json  TEXT    NOT NULL,
    UNIQUE (run_id, record_index)
);

CREATE TABLE IF NOT EXISTS record_events (
    id            INTEGER PRIMARY KEY,
    record_id     INTEGER NOT NULL REFERENCES records(id),
    run_stage_id  INTEGER NOT NULL REFERENCES run_stages(id),
    at            TEXT    NOT NULL,
    status        TEXT    NOT NULL CHECK (status IN ('ok', 'dropped', 'error')),
    input_json    TEXT    NOT NULL,
    output_json   TEXT,
    error_type    TEXT,
    error_message TEXT,
    error_traceback TEXT,
    duration_us   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_records_run   ON records (run_id, record_index);
CREATE INDEX IF NOT EXISTS idx_events_record ON record_events (record_id);
CREATE INDEX IF NOT EXISTS idx_events_stage  ON record_events (run_stage_id, status);

-- a run's status is derived from its events, because updating the run row would
-- break the append-only rule
CREATE VIEW IF NOT EXISTS run_status AS
SELECT r.id AS run_id,
       r.started_at,
       (SELECT e.at   FROM run_events e
         WHERE e.run_id = r.id AND e.kind != 'started'
         ORDER BY e.id DESC LIMIT 1) AS ended_at,
       COALESCE((SELECT e.kind FROM run_events e
                  WHERE e.run_id = r.id ORDER BY e.id DESC LIMIT 1), 'started') AS status
FROM runs r;
