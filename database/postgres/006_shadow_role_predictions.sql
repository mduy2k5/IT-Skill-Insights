-- 006_shadow_role_predictions.sql
-- Persistent shadow logging table for JobBERT V3 title classification.
-- Holds shadow inferences, confidence scores, human review status, and A/B comparison with ruleset v0.1.
-- This data is isolated and NOT joined into live OLAP skill aggregations until promoted.

CREATE TABLE IF NOT EXISTS shadow_job_role_predictions (
    prediction_id BIGSERIAL PRIMARY KEY,
    job_id UUID REFERENCES jobs(job_id) ON DELETE SET NULL,
    source_job_key VARCHAR(120),
    model_version VARCHAR(80) NOT NULL,
    input_title_raw TEXT NOT NULL,
    input_title_cleaned TEXT NOT NULL,
    predicted_family VARCHAR(100) NOT NULL,
    confidence_score NUMERIC(6, 4) NOT NULL,
    margin_score NUMERIC(6, 4) NOT NULL,
    decision_status VARCHAR(50) NOT NULL, -- 'AUTO_ASSIGNED', 'AMBIGUOUS_REVIEW', 'LOW_CONFIDENCE_REVIEW'
    candidate_families JSONB,
    rule_v0_1_prediction VARCHAR(100),
    human_review_status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'verified', 'corrected'
    human_reviewed_family VARCHAR(100),
    is_match_reviewed BOOLEAN,
    is_false_merge BOOLEAN DEFAULT FALSE,
    evaluated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_job_model UNIQUE (source_job_key, model_version)
);

CREATE INDEX IF NOT EXISTS idx_shadow_decision ON shadow_job_role_predictions(decision_status);
CREATE INDEX IF NOT EXISTS idx_shadow_review_status ON shadow_job_role_predictions(human_review_status);

GRANT SELECT, INSERT, UPDATE ON shadow_job_role_predictions TO job_pipeline;
GRANT SELECT ON shadow_job_role_predictions TO job_web_reader;
