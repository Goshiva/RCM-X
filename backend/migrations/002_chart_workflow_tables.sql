CREATE TABLE IF NOT EXISTS charts (
    chart_id BIGSERIAL PRIMARY KEY,
    file_path TEXT NOT NULL UNIQUE,
    original_filename VARCHAR(255) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued','assigned','locked','in_progress','pending_audit','audit_locked','audited','completed','failed','released','archived')),
    priority INT NOT NULL DEFAULT 0,
    assigned_to_user_id BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    l1_user_id BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    l2_user_id BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    patient_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    encounter_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    category VARCHAR(100) NOT NULL DEFAULT '',
    locked_at TIMESTAMPTZ,
    locked_until TIMESTAMPTZ,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_charts_status_priority ON charts (status, priority DESC, uploaded_at ASC);
CREATE INDEX IF NOT EXISTS idx_charts_locked_until ON charts (locked_until);

-- Transactional claim pattern for PostgreSQL:
-- BEGIN;
-- SELECT chart_id FROM charts
-- WHERE status = 'queued'
-- ORDER BY priority DESC, uploaded_at ASC
-- LIMIT 1
-- FOR UPDATE SKIP LOCKED;
-- -- then update status/assignment and commit
-- COMMIT;
