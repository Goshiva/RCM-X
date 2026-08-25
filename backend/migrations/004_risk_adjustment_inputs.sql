CREATE TABLE IF NOT EXISTS risk_adjustment_inputs (
    input_id BIGSERIAL PRIMARY KEY,
    chart_id BIGINT NOT NULL REFERENCES charts(chart_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE SET NULL,
    user_inputs JSONB NOT NULL DEFAULT '{}'::jsonb,
    captured_icd10_codes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    mapped_hcc_versions JSONB NOT NULL DEFAULT '[]'::jsonb,
    calculated_raf_score NUMERIC(8,4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_inputs_chart_user ON risk_adjustment_inputs (chart_id, user_id);
