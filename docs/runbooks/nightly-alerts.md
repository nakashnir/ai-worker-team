# A12 — Nightly Alerts Runbook

## What this adds

A12 extends the existing nightly regression workflow with optional webhook alerting.
It is additive only: no services, ports, or backend routes are changed.

| Behaviour | Detail |
|-----------|--------|
| On nightly failure | Sends alert by default |
| On nightly success | Skipped by default; opt in with `ALERT_ON_SUCCESS=true` |
| No webhook configured | Skipped safely; job exits 0 |
| Webhook delivery fails | Warning logged; job exits 0 |

Alerting is **non-fatal**. It will never block or fail the nightly workflow.

---

## Files added

| Path | Purpose |
|------|---------|
| `.github/workflows/nightly-alerts.yml` | Alert workflow, triggered by nightly regression completion |
| `.github/scripts/nightly_alert.py` | Alert sender script (generic JSON webhook POST) |
| `docs/runbooks/nightly-alerts.md` | This file |

No existing files are modified.

---

## Payload format

A12 sends a **generic JSON webhook payload**. It is not pre-formatted for any
specific channel. To deliver to Slack, Teams, PagerDuty, Discord, or similar
services, route `ALERT_WEBHOOK_URL` through an adapter, or extend
`nightly_alert.py` with channel-specific formatting in a future ticket.

### Example payload — failure with full artifact

```json
{
  "event": "nightly_regression",
  "status": "failure",
  "pass_fail": "fail",
  "task_id": "a3f1c2d4-8b7e-4f2a-9c1d-0e5f6a7b8c9d",
  "model": "anthropic:claude-sonnet-4-5-20250929",
  "dataset_path": "datasets/nightly_eval_curated_v1.jsonl",
  "exact_match_rate": 0.7,
  "timestamp": "2026-03-20T02:14:33+00:00",
  "github_run_url": "https://github.com/org/ai-worker-team/actions/runs/123456789",
  "workflow_name": "Nightly Regression",
  "repo": "org/ai-worker-team",
  "run_id": "123456789"
}
```

### Example payload — failure without artifact (minimum fields)

```json
{
  "event": "nightly_regression",
  "status": "failure",
  "pass_fail": "fail",
  "timestamp": "2026-03-20T02:14:33+00:00",
  "github_run_url": "https://github.com/org/ai-worker-team/actions/runs/123456789",
  "workflow_name": "Nightly Regression",
  "repo": "org/ai-worker-team",
  "run_id": "123456789"
}
```

`None`/absent fields are stripped before sending; the receiver always gets a
compact, valid JSON object.

---

## Configuration

### Required secret

| Name | Description |
|------|-------------|
| `ALERT_WEBHOOK_URL` | Webhook endpoint that accepts a JSON `POST`. Set in **Settings → Secrets → Actions**. |

### Optional repository variable

| Name | Default | Description |
|------|---------|-------------|
| `ALERT_ON_SUCCESS` | `false` | Set to `true` to send a payload on successful runs too. Set in **Settings → Variables → Actions**. |

### Example `.env` for local testing

```
ALERT_WEBHOOK_URL=https://your-test-endpoint.example.com/hooks/nightly
ALERT_ON_SUCCESS=false
NIGHTLY_STATUS=failure
ALERT_SUMMARY_FILE=/tmp/nightly-alert/regression-summary.json
```

---

## How the optional artifact works

If the nightly regression workflow uploads an artifact named **`regression-summary`**
containing a file `regression-summary.json`, the alert will include richer fields
(`task_id`, `model`, `dataset_path`, `exact_match_rate`, `pass_fail`).

If the artifact is absent or cannot be downloaded, the alert is still sent with
whatever workflow-level metadata is available. The download step exits cleanly.

### Minimal `regression-summary.json` schema

```json
{
  "task_id": "<string>",
  "status": "<string>",
  "model": "<string>",
  "dataset_path": "<string>",
  "exact_match_rate": "<float>",
  "pass_fail": "pass | fail",
  "timestamp": "<ISO-8601 string>"
}
```

All fields are optional. Any subset is accepted.

---

## Validation steps

### 1 — Confirm workflow name matches

Open `.github/workflows/nightly-alerts.yml` and check that the names under
`workflow_run.workflows:` match the exact `name:` field of your nightly workflow:

```yaml
workflows:
  - Nightly Regression
  - nightly-regression
```

Add or adjust entries to match your repo's actual workflow name.

### 2 — Test with a live webhook endpoint

Use a free inspection service (e.g. `webhook.site`) to capture the raw payload:

```bash
# Set the secret in GitHub:
# Settings → Secrets and variables → Actions → New repository secret
# Name: ALERT_WEBHOOK_URL
# Value: https://webhook.site/<your-uuid>
```

### 3 — Trigger a test run

```bash
# Trigger the nightly regression workflow manually:
gh workflow run nightly_eval.yml --ref main

# Then watch the alert workflow:
gh run list --workflow=nightly-alerts.yml
gh run watch
```

### 4 — Smoke-test the script locally

```bash
cd /path/to/ai-worker-team-repo

# Test: no webhook configured — must exit 0
python3 .github/scripts/nightly_alert.py
# Expected: [nightly-alert] ALERT_WEBHOOK_URL not set — skipping alert (non-fatal).

# Test: failure alert
ALERT_WEBHOOK_URL=https://webhook.site/<uuid> \
NIGHTLY_STATUS=failure \
GITHUB_RUN_URL=https://github.com/org/repo/actions/runs/1 \
WORKFLOW_NAME="Nightly Regression" \
GITHUB_REPOSITORY=org/repo \
GITHUB_RUN_ID=1 \
  python3 .github/scripts/nightly_alert.py
# Expected: [nightly-alert] sending alert for status='failure' ...
#           [nightly-alert] alert sent (HTTP 200)

# Test: success with ALERT_ON_SUCCESS=false (default) — must skip
ALERT_WEBHOOK_URL=https://webhook.site/<uuid> \
NIGHTLY_STATUS=success \
  python3 .github/scripts/nightly_alert.py
# Expected: [nightly-alert] status='success' and ALERT_ON_SUCCESS=false — skipping.

# Test: success with ALERT_ON_SUCCESS=true — must send
ALERT_WEBHOOK_URL=https://webhook.site/<uuid> \
NIGHTLY_STATUS=success \
ALERT_ON_SUCCESS=true \
  python3 .github/scripts/nightly_alert.py
# Expected: [nightly-alert] sending alert for status='success' ...
#           [nightly-alert] alert sent (HTTP 200)

# Test: bad webhook URL — must exit 0 (non-fatal)
ALERT_WEBHOOK_URL=https://invalid.example.invalid/hook \
NIGHTLY_STATUS=failure \
  python3 .github/scripts/nightly_alert.py
# Expected: [nightly-alert] warning: webhook delivery failed: ...
#           (exits 0)
```

### 5 — Confirm no regressions in existing stack

```bash
curl -sf http://127.0.0.1:8080/health
# Expected: {"status":"ok"}

curl -sf http://127.0.0.1:8080/schemas | python3 -c \
  "import sys,json; print(list(json.load(sys.stdin).keys()))"
# Expected: ['task_schema', 'task_result_schema']
```

These endpoints are unchanged. A12 touches no backend code.

---

## Rollback

A12 is purely additive. To disable alerting without deleting files:

1. Remove (or do not set) the `ALERT_WEBHOOK_URL` secret — the alert job will
   skip safely on every run.
2. To stop the workflow from running at all, rename or delete
   `.github/workflows/nightly-alerts.yml`.

No orchestrator restart or DB change is required.
