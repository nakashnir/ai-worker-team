-- ─────────────────────────────────────────────────────────────────
-- EvalOps schema — Ticket #A3
-- Safe to run multiple times: all statements use IF NOT EXISTS.
-- ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS eval_runs (
    task_id       TEXT        PRIMARY KEY,
    dataset_path  TEXT        NOT NULL,
    model         TEXT        NOT NULL,
    scorers       JSONB       NOT NULL,
    status        TEXT        NOT NULL,
    metrics       JSONB       NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS eval_samples (
    task_id    TEXT  NOT NULL REFERENCES eval_runs(task_id) ON DELETE CASCADE,
    sample_id  TEXT  NOT NULL,
    prompt     TEXT  NOT NULL,
    expected   TEXT,
    output     TEXT  NOT NULL,
    scores     JSONB NOT NULL,
    PRIMARY KEY (task_id, sample_id)
);

CREATE INDEX IF NOT EXISTS idx_eval_samples_task_id
    ON eval_samples (task_id);
