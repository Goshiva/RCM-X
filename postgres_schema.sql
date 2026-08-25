-- PostgreSQL schema for the Risk Adjustment Tool
-- Supports users, charts, risk-adjustment inputs, and HIPAA-compliant audit logging

CREATE TYPE user_role AS ENUM ('coder', 'master_admin');

CREATE TABLE users (
    user_id BIGSERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'coder',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE charts (
    chart_id BIGSERIAL PRIMARY KEY,
    file_path TEXT NOT NULL UNIQUE,
    status VARCHAR(30) NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'assigned', 'in_progress', 'completed', 'failed', 'archived')),
    assigned_to_user_id BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    locked_at TIMESTAMPTZ,
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE risk_adjustment_inputs (
    input_id BIGSERIAL PRIMARY KEY,
    chart_id BIGINT NOT NULL REFERENCES charts(chart_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE SET NULL,
    user_inputs JSONB NOT NULL DEFAULT '{}'::jsonb,
    captured_icd10_codes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    mapped_hcc_versions JSONB NOT NULL DEFAULT '[]'::jsonb,
    calculated_raf_score NUMERIC(8, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE audit_logs (
    audit_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    chart_id BIGINT REFERENCES charts(chart_id) ON DELETE SET NULL,
    action_type VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id VARCHAR(255),
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_charts_updated_at
BEFORE UPDATE ON charts
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_risk_adjustment_inputs_updated_at
BEFORE UPDATE ON risk_adjustment_inputs
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE INDEX idx_charts_status_assigned
    ON charts (status, assigned_to_user_id);

CREATE INDEX idx_charts_locked_until
    ON charts (locked_until);

CREATE INDEX idx_risk_adjustment_inputs_chart_user
    ON risk_adjustment_inputs (chart_id, user_id);

CREATE INDEX idx_audit_logs_created_at
    ON audit_logs (created_at DESC);

CREATE INDEX idx_audit_logs_chart_user
    ON audit_logs (chart_id, user_id);

-- Example transactional chart assignment query for the "Get Chart" button.
-- This uses a row-level lock so two users cannot grab the same chart at the same time.

-- Example 1: lock a specific chart before assignment
-- BEGIN;
-- SELECT chart_id, status, assigned_to_user_id
-- FROM charts
-- WHERE chart_id = $1
-- FOR UPDATE;
--
-- UPDATE charts
-- SET status = 'assigned',
--     assigned_to_user_id = $2,
--     locked_at = NOW(),
--     locked_until = NOW() + INTERVAL '30 minutes'
-- WHERE chart_id = $1;
--
-- INSERT INTO audit_logs (user_id, chart_id, action_type, entity_type, details)
-- VALUES ($2, $1, 'chart_assigned', 'chart', JSONB_BUILD_OBJECT('assigned_by', $2));
-- -- COMMIT;

-- Example 2: safely claim the next available chart for a coder
-- BEGIN;
-- SELECT chart_id
-- FROM charts
-- WHERE status = 'queued'
-- ORDER BY created_at
-- LIMIT 1
-- FOR UPDATE SKIP LOCKED;
--
-- -- Then update the selected chart and insert an audit record.
-- -- COMMIT;
