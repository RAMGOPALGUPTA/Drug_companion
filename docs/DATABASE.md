# Database

PostgreSQL 16.

Schema source of truth: infra/schema.sql

Tables:
- operators
- model_registry
- cases
- analysis_runs
- evidence
- audit_log

analysis_runs stores structured JSON for each pipeline stage so a result can be reconstructed without collapsing the pipeline into one opaque value.
