-- OmniSeed database schema
-- Design principle: raw payload content is never stored here, by design.
-- The `jobs` table tracks lifecycle only; `analysis_results` holds the
-- long-term metadata/summary output that the retention policy permits.

-- Tracks job lifecycle for auditing, never stores payload content
CREATE TABLE jobs (
    job_id UUID PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('iot', 'wearable', 'upload')),
    status TEXT NOT NULL CHECK (status IN ('received', 'processing', 'summarized', 'failed', 'raw_deleted')),
    received_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    error_message TEXT
);

-- The only long-term data store — metadata + summaries, no raw content
CREATE TABLE analysis_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(job_id),
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    tags TEXT[],
    anomaly_flag BOOLEAN DEFAULT FALSE,
    prompt_version TEXT NOT NULL DEFAULT 'v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Registry of known sources (devices, wearable accounts, upload channels).
-- The polling scheduler should read from this table in production instead
-- of hardcoding pollers.
CREATE TABLE sources (
    source_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    display_name TEXT,
    poll_endpoint TEXT,       -- null for push sources
    poll_interval_minutes INT,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Useful indexes for the UI's browse/filter views
CREATE INDEX idx_results_source_type ON analysis_results(source_type);
CREATE INDEX idx_results_created_at ON analysis_results(created_at);
CREATE INDEX idx_jobs_status ON jobs(status);
