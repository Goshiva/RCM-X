CREATE TABLE IF NOT EXISTS jobs (
    task_id VARCHAR(255) PRIMARY KEY,
    chart_id BIGINT NOT NULL REFERENCES charts(chart_id) ON DELETE CASCADE,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_chart_status ON jobs (chart_id, status);
