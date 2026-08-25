ALTER TABLE charts
    ADD COLUMN IF NOT EXISTS l1_user_id BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS l2_user_id BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS patient_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS encounter_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS category VARCHAR(100) NOT NULL DEFAULT '';

ALTER TABLE charts DROP CONSTRAINT IF EXISTS charts_status_check;
ALTER TABLE charts ADD CONSTRAINT charts_status_check CHECK (
    status IN ('queued','assigned','locked','in_progress','pending_audit','audit_locked','audited','completed','failed','released','archived')
);

CREATE INDEX IF NOT EXISTS idx_charts_audit_bucket ON charts (status, l2_user_id);