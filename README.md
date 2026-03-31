# ai-worker-team

`ai-worker-team` is an EvalOps / LLM Quality Lab repository for running structured evaluation jobs, storing artifacts/results, and exposing regression signals through dashboard views and nightly CI checks. The project focuses on making evaluation behavior visible, repeatable, and operationally useful across local execution and scheduled workflows.

## Problem Statement

Teams shipping LLM-backed features need a practical way to answer three recurring questions: did quality regress, where did it regress, and how quickly can that change be surfaced. Many teams have partial tooling, but lack a single, operational workflow for running evals, storing outcomes, and reviewing regressions.

## What the System Does

- Runs evaluation tasks against configured models/providers.
- Persists run-level and sample-level results.
- Writes artifacts for reports and run history.
- Exposes dashboard views for run inspection and run-to-run comparison.
- Executes nightly regression checks in GitHub Actions.
- Sends webhook-based nightly alerts, including Discord-compatible notifications.

## Architecture Overview

High-level components:

- `orchestrator`: API + dashboard service for task submission, run queries, and UI.
- `workers`: background execution service for eval tasks and artifact generation.
- `postgres` + `redis`: persistence and queue/state coordination.
- `shared/`: datasets plus runtime artifact directories (runs/reports/docs).
- GitHub Actions: scheduled nightly eval + alerting workflow.

## Core Workflows

1. Submit an eval task.
2. Worker executes samples and computes metrics.
3. Results and artifacts are written to storage.
4. Dashboard surfaces run details and comparison views.
5. Nightly workflow executes regression checks and emits alerts.

## Key Features

- Eval run execution and metric reporting.
- Run detail inspection with sample-level visibility.
- Compare-runs view for regression checks.
- Nightly regression automation (A8).
- Dashboard read-only base (A9) and polish/safe metric rendering (A10).
- Compare-runs + regression visibility updates (A11).
- Nightly alerts + regression summary + Discord webhook path (A12).

## Screenshots / Demo

Dashboard overview.

![Dashboard overview](docs/assets/dashboard-main.png)

Run detail.

![Run detail](docs/assets/run-detail.png)

Compare runs.

![Compare runs](docs/assets/compare-runs.png)

GitHub Actions nightly workflow.

![GitHub Actions nightly workflow](docs/assets/github-actions-nightly-eval.png)

Discord alert.

![Discord alert](docs/assets/discord-alert-success.png)

## Repository Structure

```text
.
├── orchestrator/        # API service + dashboard templates/static
├── workers/             # background worker execution logic
├── providers/           # model/provider integrations and fallback handling
├── schemas/             # task/result schema contracts
├── ops/sql/             # database schema/init SQL
├── scripts/             # local workflow utilities and regression checks
├── .github/workflows/   # nightly CI workflows
├── docs/                # public docs/runbooks
├── baselines/           # regression baseline contracts
└── shared/              # datasets and runtime artifact directories
```

## Tech Stack

- Python 3.11+
- FastAPI + Uvicorn
- Jinja2 templates + static dashboard assets
- Redis
- PostgreSQL
- Docker Compose
- GitHub Actions

## How to Run Locally

```bash
# 1) Clone and enter repository
cd /path/to/ai-worker-team-repo

# 2) Create .env (example values)
cat > .env <<'ENV'
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=ai_workers
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DEFAULT_ANTHROPIC_MODEL=claude-sonnet-4-5-20250929
ENV

# 3) Start stack
docker-compose up -d

# 4) Initialize schema
docker-compose exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U postgres -d ai_workers \
  < ops/sql/001_evalops.sql

# 5) Run nightly regression script locally
./scripts/run_nightly_local.sh
```

## GitHub Actions / Nightly Usage

- `nightly_eval.yml` schedules regression execution and artifact upload.
- `nightly-alerts.yml` listens for nightly completion and sends webhook alerts.
- Alerting is non-fatal by design; regression workflows continue even if webhook delivery fails.

For operational details, see:

- `RUNBOOK.md`
- `docs/runbooks/nightly-alerts.md`

## Configuration / Env

Primary environment variables used across services/workflows:

- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `REDIS_URL`
- `SHARED_DIR`
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `DEFAULT_ANTHROPIC_MODEL`
- `ALERT_WEBHOOK_URL`
- `ALERT_ON_SUCCESS`

## Limitations

- Historical analytics are limited: the project surfaces run-level comparisons and nightly pass/fail checks, but does not yet provide dedicated long-horizon trend dashboards.
- Scoring is intentionally focused on current regression workflows; broader rubric/benchmark coverage is still in progress.
- Alerting is webhook-first and CI-driven; advanced routing/escalation policies are not yet built in.

## Future Work

- Expand benchmark datasets and scorer coverage.
- Harden deployment packaging and environment profiles.
- Add richer observability and trend visualization.
- Add more complete contributor and operations documentation.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
