# RUNBOOK - A8 v2 Nightly Regression

## Scope

This repo includes a nightly regression workflow for `eval.run` on
`shared/datasets/nightly_eval_curated_v1.jsonl`.

Files added for A8 v2:

- `.github/workflows/nightly_eval.yml`
- `scripts/run_nightly_local.sh`
- `scripts/check_regression.py`
- `baselines/eval_valid_v1_baseline.json`

## Prerequisites

- Orchestrator reachable at `http://127.0.0.1:8080` (or set `ORCH_URL`)
- Worker stack running and able to process `eval.run`
- `curl` and `python3` available

## Local run

```bash
cd /path/to/ai-worker-team-repo
chmod +x scripts/run_nightly_local.sh
./scripts/run_nightly_local.sh
```

Optional overrides:

```bash
ORCH_URL=http://127.0.0.1:8080 \
DATASET_PATH=shared/datasets/nightly_eval_curated_v1.jsonl \
MODEL=anthropic:claude-sonnet-4-5-20250929 \
./scripts/run_nightly_local.sh
```

## What the nightly script does

1. Submits `POST /task/submit` with `task_type=eval.run`
2. Polls `GET /task/status/{task_id}` until `done`
3. Fetches `GET /eval/run/{task_id}` into `shared/reports/nightly_*_eval_run.json`
4. Runs `scripts/check_regression.py` against the baseline

## Baseline contract

`baselines/eval_valid_v1_baseline.json` enforces:

- dataset path equals the nightly dataset configured for the run
- scorers list equals `["exact_match","contains_expected","format_nonempty"]`
- `metrics.exact_match_rate >= 1.0`
- `metrics.passed == true`

For this curated nightly path, align the baseline dataset path to
`shared/datasets/nightly_eval_curated_v1.jsonl`.
Adjust thresholds in that baseline file when intentionally changing expectations.
Keep `shared/datasets/sample_eval_valid_v1.jsonl` available as a smoke/sample fixture.

## GitHub workflow

Workflow: `.github/workflows/nightly_eval.yml`

- scheduled daily at `03:15` UTC
- supports manual trigger (`workflow_dispatch`)
- executes `./scripts/run_nightly_local.sh`

### V-3 — Get single run with artifact paths

```bash
# 20. Detail for a known task_id (use TASK_ID from step 15)
curl -sf "http://127.0.0.1:8080/eval/run/${TASK_ID}" | python3 -m json.tool
```

**Expected shape:**
```json
{
  "task_id":       "...",
  "dataset_path":  "datasets/nightly_eval_curated_v1.jsonl",
  "model":         "anthropic:claude-sonnet-4-5-20250929",
  "scorers":       ["exact_match", "contains_expected", "format_nonempty"],
  "status":        "done",
  "metrics":       { "total": 10, "elapsed_ms_total": ..., "usage": {...}, ... },
  "created_at":    "2026-...",
  "completed_at":  "2026-...",
  "report_path":   "/app/shared/reports/..._eval_report.md",
  "results_path":  "/app/shared/runs/.../eval_results.jsonl"
}
```

Note: `report_path` and `results_path` are non-null only when the run was completed
by the A5/A6 worker (which writes run.json with a `summary` block).

```bash
# 21. Confirm 404 on non-existent task_id
curl -o /dev/null -w "%{http_code}" \
  http://127.0.0.1:8080/eval/run/does-not-exist-000
```

**Expected:** `404`

---

### V-4 — Samples pagination

```bash
# 22. First page: 3 samples
curl -sf "http://127.0.0.1:8080/eval/run/${TASK_ID}/samples?limit=3&offset=0" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'count={d[\"count\"]}  total={d[\"total\"]}  limit={d[\"limit\"]}  offset={d[\"offset\"]}')
for s in d['samples']:
    print(' ', s['sample_id'], '|', s['output'][:40])
"
```

**Expected:** `count=3  total=10  limit=3  offset=0`, three sample rows

```bash
# 23. Second page: samples 4–6
curl -sf "http://127.0.0.1:8080/eval/run/${TASK_ID}/samples?limit=3&offset=3" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'count={d[\"count\"]}  total={d[\"total\"]}  offset={d[\"offset\"]}')
for s in d['samples']:
    print(' ', s['sample_id'])
"
```

**Expected:** `offset=3`, different `sample_id` values from page 1

```bash
# 24. Last page: samples 9–10 (offset 9, limit 3 → count=1)
curl -sf "http://127.0.0.1:8080/eval/run/${TASK_ID}/samples?limit=3&offset=9" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'count={d[\"count\"]}  total={d[\"total\"]}  offset={d[\"offset\"]}')
"
```

**Expected:** `count=1  total=10  offset=9`

---

### V-5 — Samples search with `q=`

> The substring search is case-insensitive and checks `prompt`, `expected`, and `output`.
> Use a substring that appears in your dataset. The example below uses `"Paris"` — replace
> with a term that actually appears in your `nightly_eval_curated_v1.jsonl` prompts.

```bash
# 25. Search: substring in prompt/expected/output
Q_TERM="Paris"    # replace with a term present in your dataset
curl -sf "http://127.0.0.1:8080/eval/run/${TASK_ID}/samples?q=${Q_TERM}" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'q={d.get(\"q\",\"(not echoed)\")}  count={d[\"count\"]}  total={d[\"total\"]}')
for s in d['samples']:
    print(' ', s['sample_id'], '|', s['prompt'][:60])
"
```

**Expected:** only samples whose `prompt`, `expected`, or `output` contains `Paris` (case-insensitive)

```bash
# 26. Search for a term unlikely to exist → count=0
curl -sf "http://127.0.0.1:8080/eval/run/${TASK_ID}/samples?q=xyzzy_no_match_9999" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'count={d[\"count\"]}  total={d[\"total\"]}')
"
```

**Expected:** `count=0  total=0`

```bash
# 27. Exact sample_id filter
FIRST_SAMPLE=$(curl -sf \
  "http://127.0.0.1:8080/eval/run/${TASK_ID}/samples?limit=1&offset=0" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['samples'][0]['sample_id'])")

curl -sf "http://127.0.0.1:8080/eval/run/${TASK_ID}/samples?sample_id=${FIRST_SAMPLE}" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'count={d[\"count\"]}  sample_id={d[\"samples\"][0][\"sample_id\"] if d[\"samples\"] else \"none\"}')
"
```

**Expected:** `count=1`, returned `sample_id` matches `$FIRST_SAMPLE`

---

### V-6 — Pagination: `since` / `until` date filter

```bash
# 28. Runs completed today or later
TODAY=$(date -u +%Y-%m-%dT00:00:00Z)
curl -sf "http://127.0.0.1:8080/eval/runs?since=${TODAY}&limit=10" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'since today: count={d[\"count\"]}  total={d[\"total\"]}')
"
```

**Expected:** all returned rows have `completed_at` (or `created_at`) >= today

```bash
# 29. Invalid status → 422 (not 500)
curl -o /dev/null -w "%{http_code}" \
  "http://127.0.0.1:8080/eval/runs?status=nonsense"
```

**Expected:** `422`

---

## Rollback

```bash
# R-1. Bring orchestrator down
cd /path/to/ai-worker-team-repo
docker-compose stop orchestrator
docker-compose rm -f orchestrator

# R-2. If you maintain local backups, restore them per your environment policy.
# R-3. No DB changes — no psql rollback needed.
# R-4. No worker changes — worker stays running.

# R-5. Rebuild and restart
docker-compose build --no-cache orchestrator
docker-compose up -d orchestrator

# R-6. Confirm
curl -sf http://127.0.0.1:8080/health
```

---

## File tree (changed files only)

```
ai-worker-team-repo/
└── orchestrator/
    ├── app.py       <- UPDATED v1.7.0
    │                   /eval/runs      filters: status, model, provider, passed,
    │                                            since, until, sort, order, limit, offset
    │                   /eval/run/{id}  adds report_path, results_path
    │                   /eval/run/{id}/samples  filters: sample_id, q; pagination
    │                   Pydantic response models: EvalRunRow, EvalRunsResponse,
    │                                             EvalSampleRow, EvalSamplesResponse
    │                   Safe parameterized SQL throughout
    └── Dockerfile   <- unchanged (reproduced for reference)
```

Not touched: `workers/`, `providers/`, `schemas/`, `docker-compose.yml`,
`ops/sql/`, `shared/`.
