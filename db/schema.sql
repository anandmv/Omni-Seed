-- OmniSeed database schema (SQLite)
--
-- Design principle: raw payload content is never stored here, by design.
-- `jobs` doubles as both the lifecycle/audit table AND the work queue —
-- collector processes insert rows with status='received', the analyser
-- worker polls for status='received' rows, claims one, processes it, and
-- advances its status. `analysis_results` holds the long-term
-- metadata/summary output that the retention policy permits.
--
-- Notes on SQLite-specific choices:
--   - No native UUID type -> stored as TEXT (generate with uuid4() in Python)
--   - No TIMESTAMPTZ -> stored as TEXT in ISO 8601 (UTC)
--   - No native array type -> `tags` stored as a JSON-encoded TEXT column
--   - `envelope_json` holds the full ingestion envelope (source_type,
--     source_id, raw_payload/scratch_path) so the worker has everything
--     it needs to process the job without a separate message broker

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('iot', 'wearable', 'upload')),
    status TEXT NOT NULL CHECK (status IN ('received', 'processing', 'summarized', 'failed', 'raw_deleted')),
    envelope_json TEXT NOT NULL,
    received_at TEXT NOT NULL,
    completed_at TEXT,
    error_message TEXT,
    locked_by TEXT,          -- worker id currently processing this job, if any
    locked_at TEXT
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(job_id),
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    tags TEXT,               -- JSON-encoded array, e.g. '["temperature","spike"]'
    anomaly_flag INTEGER NOT NULL DEFAULT 0 CHECK (anomaly_flag IN (0, 1)),
    prompt_version TEXT NOT NULL DEFAULT 'v2',
    measurements TEXT,
    system_fingerprint TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    display_name TEXT,
    poll_endpoint TEXT,       -- null for push sources
    poll_interval_minutes INTEGER,
    registered_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- The core queue-lookup index: workers scan for the oldest pending job.
CREATE INDEX IF NOT EXISTS idx_jobs_status_received ON jobs(status, received_at);
CREATE INDEX IF NOT EXISTS idx_results_source_type ON analysis_results(source_type);
CREATE INDEX IF NOT EXISTS idx_results_created_at ON analysis_results(created_at);
