-- Drug Companion database schema
-- PostgreSQL 16+
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS operators (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS model_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    artifact_sha256 TEXT NOT NULL CHECK (artifact_sha256 ~ '^[a-f0-9]{64}$'),
    architecture TEXT NOT NULL,
    model_format TEXT NOT NULL CHECK (model_format IN ('tflite', 'keras', 'onnx', 'other')),
    quantization TEXT CHECK (quantization IS NULL OR quantization IN ('none', 'fp32', 'fp16', 'int8', 'other')),
    input_width INTEGER NOT NULL CHECK (input_width > 0),
    input_height INTEGER NOT NULL CHECK (input_height > 0),
    channels INTEGER NOT NULL CHECK (channels IN (1, 3, 4)),
    normalization TEXT NOT NULL,
    class_labels JSONB NOT NULL,
    model_type TEXT NOT NULL CHECK (model_type IN ('bootstrap', 'synthetic_demo', 'target_candidate', 'target_validated')),
    target_validated BOOLEAN NOT NULL DEFAULT FALSE,
    production_approved BOOLEAN NOT NULL DEFAULT FALSE,
    forensic_status TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (model_name, model_version)
);

CREATE TABLE IF NOT EXISTS cases (
    id UUID PRIMARY KEY,
    operator_id TEXT NOT NULL REFERENCES operators(id),
    classification TEXT NOT NULL CHECK (classification IN ('positive', 'negative', 'inconclusive')),
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    latitude DOUBLE PRECISION CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    longitude DOUBLE PRECISION CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    captured_at TIMESTAMPTZ NOT NULL,
    model_version TEXT NOT NULL,
    app_version TEXT NOT NULL,
    sync_status TEXT NOT NULL DEFAULT 'synced' CHECK (sync_status IN ('pending', 'synced', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    model_registry_id UUID REFERENCES model_registry(id),
    pipeline_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    final_classification TEXT CHECK (final_classification IS NULL OR final_classification IN ('positive', 'negative', 'inconclusive')),
    final_confidence DOUBLE PRECISION CHECK (final_confidence IS NULL OR final_confidence BETWEEN 0 AND 1),
    ml_classification TEXT CHECK (ml_classification IS NULL OR ml_classification IN ('positive', 'negative', 'invalid')),
    ml_confidence DOUBLE PRECISION CHECK (ml_confidence IS NULL OR ml_confidence BETWEEN 0 AND 1),
    quality_gate JSONB NOT NULL DEFAULT '{}'::jsonb,
    calibration JSONB NOT NULL DEFAULT '{}'::jsonb,
    roi_extraction JSONB NOT NULL DEFAULT '{}'::jsonb,
    rule_engine JSONB NOT NULL DEFAULT '{}'::jsonb,
    ml_inference JSONB NOT NULL DEFAULT '{}'::jsonb,
    arbitration JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_code TEXT,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((status = 'completed' AND completed_at IS NOT NULL) OR status IN ('running', 'failed'))
);

CREATE TABLE IF NOT EXISTS evidence (
    case_id UUID PRIMARY KEY REFERENCES cases(id) ON DELETE CASCADE,
    analysis_run_id UUID REFERENCES analysis_runs(id) ON DELETE SET NULL,
    image_sha256 TEXT NOT NULL CHECK (image_sha256 ~ '^[a-f0-9]{64}$'),
    payload_sha256 TEXT NOT NULL CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
    evidence_packet_sha256 TEXT CHECK (evidence_packet_sha256 IS NULL OR evidence_packet_sha256 ~ '^[a-f0-9]{64}$'),
    image_size BIGINT CHECK (image_size IS NULL OR image_size >= 0),
    image_mime TEXT CHECK (image_mime IS NULL OR image_mime IN ('image/jpeg', 'image/png', 'image/webp')),
    schema_version TEXT NOT NULL DEFAULT '1.0.0',
    integrity_status TEXT NOT NULL DEFAULT 'verified' CHECK (integrity_status IN ('verified', 'review', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE,
    operator_id TEXT REFERENCES operators(id),
    action TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cases_captured_at ON cases(captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_cases_classification ON cases(classification);
CREATE INDEX IF NOT EXISTS idx_cases_operator_captured ON cases(operator_id, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_case_created ON analysis_runs(case_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_status ON analysis_runs(status);
CREATE INDEX IF NOT EXISTS idx_evidence_integrity ON evidence(integrity_status);
CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_log(case_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_operator ON audit_log(operator_id, created_at DESC);

INSERT INTO operators(id, display_name)
VALUES ('demo-operator', 'Demo Operator')
ON CONFLICT (id) DO NOTHING;
