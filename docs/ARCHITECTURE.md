# Architecture Documentation

## System Overview

`ai-worker-team` implements a task queue architecture for LLM evaluation operations with persistent storage, diagnostic visibility, and CI integration.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
├─────────────────────────────────────────────────────────────────┤
│  • Local scripts (run_nightly_local.sh)                         │
│  • GitHub Actions (nightly_eval.yml, nightly-alerts.yml)        │
│  • Direct API clients                                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR LAYER                            │
├─────────────────────────────────────────────────────────────────┤
│  FastAPI Application (orchestrator/app.py)                      │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │   API Routes     │  │   Dashboard      │                    │
│  │  /task/submit    │  │  /dashboard      │                    │
│  │  /task/status    │  │  /dashboard/run  │                    │
│  │  /eval/runs      │  │  /dashboard/cmp  │                    │
│  └──────────────────┘  └──────────────────┘                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      QUEUE LAYER                                 │
├─────────────────────────────────────────────────────────────────┤
│  Redis                                                           │
│  • Task queue (queue:eval_tasks)                                │
│  • In-progress tracking (inprogress:*)                          │
│  • Coordination primitives                                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EXECUTION LAYER                               │
├─────────────────────────────────────────────────────────────────┤
│  Worker Service (workers/app.py)                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  1. Poll queue for tasks                                  │  │
│  │  2. Load dataset and configuration                        │  │
│  │  3. Execute evaluation:                                    │  │
│  │     • Deterministic scorers (exact match, contains, etc)  │  │
│  │     • LLM-as-judge evaluator (structured verdict)         │  │
│  │  4. Aggregate metrics:                                     │  │
│  │     • Run-level: pass/fail, EM rate, judge pass rate      │  │
│  │     • Taxonomy: failure categories, top failure           │  │
│  │     • Verdict quality: valid verdict rate                 │  │
│  │  5. Persist results to PostgreSQL                         │  │
│  │  6. Write artifacts (JSON reports, run history)           │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PROVIDER LAYER                                │
├─────────────────────────────────────────────────────────────────┤
│  LLM Integrations (providers/)                                  │
│  • Anthropic Claude (primary)                                   │
│  • OpenAI (fallback)                                            │
│  • Retry logic with exponential backoff                         │
│  • Structured output parsing                                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STORAGE LAYER                                 │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL                                                      │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │   eval_runs      │  │  eval_samples    │                    │
│  │  • task_id       │  │  • run_id        │                    │
│  │  • status        │  │  • sample_id     │                    │
│  │  • metrics       │  │  • eval_result   │                    │
│  │  • dataset_path  │  │  • scores        │                    │
│  │  • model         │  │  • output        │                    │
│  └──────────────────┘  └──────────────────┘                    │
│                                                                  │
│  Filesystem (shared/)                                           │
│  • runs/: JSON artifacts per task_id                            │
│  • reports/: Evaluation reports                                 │
│  • docs/: Generated documentation                               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    AUTOMATION LAYER                              │
├─────────────────────────────────────────────────────────────────┤
│  GitHub Actions (.github/workflows/)                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  nightly_eval.yml:                                        │  │
│  │  • Scheduled trigger (cron)                               │  │
│  │  • Execute baseline evaluation                            │  │
│  │  • Compare against last known good                        │  │
│  │  • Upload artifacts                                        │  │
│  │  • Trigger alert workflow                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  nightly-alerts.yml:                                      │  │
│  │  • Listen for workflow completion                         │  │
│  │  • Extract regression summary                             │  │
│  │  • Send webhook (Discord-compatible)                      │  │
│  │  • Non-fatal: continue on webhook failure                 │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Evaluation Execution Flow

```
1. Task Submission
   ┌─────────────┐
   │ Client      │
   │ (API/Script)│
   └─────┬───────┘
         │
         ▼
   ┌─────────────┐
   │Orchestrator │ → Validate task schema
   │  (API)      │ → Generate task_id
   └─────┬───────┘ → Push to Redis queue
         │          → Return task_id to client
         ▼
   ┌─────────────┐
   │   Redis     │
   │   Queue     │
   └─────────────┘

2. Worker Processing
   ┌─────────────┐
   │   Worker    │ ← Poll queue for tasks
   └─────┬───────┘
         │
         ├→ Load dataset (JSONL)
         │
         ├→ For each sample:
         │   ├→ Run deterministic scorers
         │   ├→ Run LLM judge (if configured)
         │   ├→ Extract verdict & failure category
         │   └→ Persist sample result
         │
         ├→ Aggregate run-level metrics:
         │   ├→ Exact match rate
         │   ├→ Judge pass rate
         │   ├→ Failure category counts
         │   └→ Valid verdict rate
         │
         ├→ Write artifacts:
         │   ├→ runs/{task_id}/report.json
         │   └→ runs/{task_id}/samples.json
         │
         └→ Update eval_runs status → 'done'

3. Dashboard Access
   ┌─────────────┐
   │  Dashboard  │ ← Query eval_runs
   │    (UI)     │ ← Query eval_samples
   └─────┬───────┘ ← Read artifacts
         │
         ├→ /dashboard → List recent runs
         ├→ /dashboard/run/{id} → Show sample details
         └→ /dashboard/compare → Compare two runs
```

### Nightly Regression Flow

```
1. Scheduled Trigger (GitHub Actions)
   ┌─────────────────┐
   │ nightly_eval.yml│
   │ (cron: 0 2 * *) │
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ Run baseline    │ → Execute eval against baseline dataset
   │ evaluation      │ → Compare to last known good run
   └────────┬────────┘ → Determine pass/fail verdict
            │
            ├→ Pass: Regression cleared
            └→ Fail: Regression detected

2. Alert Delivery
   ┌─────────────────┐
   │nightly-alert.yml│ ← Listen for workflow completion
   └────────┬────────┘
            │
            ├→ Extract regression summary:
            │   ├→ Pass/Fail verdict
            │   ├→ EM delta
            │   ├→ Judge pass rate delta
            │   └→ Top failure category
            │
            └→ Send webhook:
                ├→ Discord (formatted embed)
                ├→ Slack (markdown blocks)
                └→ Generic webhook (JSON)
```

## Key Design Patterns

### 1. Task Queue Pattern

**Why:** Decouples task submission from execution, enables async processing, provides retry/recovery

**Implementation:**
- Orchestrator pushes tasks to Redis queue
- Workers poll queue and process tasks
- Status updates written to PostgreSQL
- Artifacts written to filesystem

**Benefits:**
- Worker-based task queue architecture supports configurable worker processes
- Resilient to worker failures
- Clear operational boundaries

### 2. Backward-Compatible Metrics

**Why:** Support legacy runs without taxonomy while enabling new diagnostic features

**Implementation:**
```python
# Safe field extraction
m = run.get("metrics") or {}
top_failure = m.get("top_failure_category")  # None for old runs
judge_rate = m.get("evaluator_pass_rate")    # None for deterministic

# Conditional rendering
{% if m.top_failure_category %}
  <tr><th>Top Failure</th><td>{{ m.top_failure_category }}</td></tr>
{% endif %}
```

**Benefits:**
- No migration required for old data
- Gradual rollout of new features
- Dashboard works for all runs

### 3. LLM-as-Judge with Structured Output

**Why:** Get reliable verdict extraction from LLM responses

**Implementation:**
```python
# Prompt for structured JSON
system_prompt = """
Return JSON: {
  "passed": true/false,
  "failure_category": "hallucination" | "incomplete_answer" | ...,
  "reasoning": "explanation"
}
"""

# Parse and validate
eval_result = parse_eval_result(llm_response)
normalized_category = normalize_failure_category(eval_result.failure_category)
```

**Benefits:**
- Reliable verdict extraction
- Taxonomy normalization
- Error handling for malformed output

### 4. Non-Fatal Alerting

**Why:** Regression checks should not fail if webhook delivery fails

**Implementation:**
```yaml
# nightly-alerts.yml
- name: Send webhook
  run: |
    curl -X POST $WEBHOOK_URL ...
  continue-on-error: true  # Never fail workflow
```

**Benefits:**
- Regression data always persisted
- Alert delivery decoupled from regression detection
- Operational resilience

## Component Details

### Orchestrator (orchestrator/app.py)

**Responsibilities:**
- Task submission API
- Dashboard serving
- Run querying and comparison
- Artifact coordination

**Key Routes:**
- `POST /task/submit` - Submit evaluation task
- `GET /task/status/{id}` - Check task status
- `GET /eval/runs` - List evaluation runs
- `GET /eval/run/{id}` - Get run details
- `GET /dashboard` - Main dashboard UI
- `GET /dashboard/run/{id}` - Run detail view
- `GET /dashboard/compare` - Compare two runs

**Design:**
- Read-only dashboard (no in-UI submission)
- Server-side rendering with Jinja2
- RESTful API design

### Workers (workers/app.py)

**Responsibilities:**
- Task execution
- LLM provider integration
- Metric aggregation
- Artifact generation

**Execution Flow:**
1. Poll Redis queue
2. Load dataset
3. Execute evaluators (deterministic + judge)
4. Aggregate metrics (run-level + taxonomy)
5. Persist results to PostgreSQL
6. Write artifacts to filesystem

**Design:**
- Stateless execution
- Retry logic with exponential backoff
- Structured error handling

### Evaluators (evals/)

**Taxonomy Module:**
- Fixed failure category set
- Normalization logic for variations
- Canonical category mapping

**Verdict Logic:**
- Deterministic: All samples exact match → PASS
- LLM Judge: All valid verdicts pass → PASS
- Hybrid: Backward compatible

**Categories:**
- `hallucination` - Factually incorrect output
- `incomplete_answer` - Missing required information
- `format_error` - Output doesn't match expected structure
- `provider_error` - LLM API failure
- `unknown` - Fallback for uncategorized failures

## Deployment Architecture

### Local Development

```
docker-compose.yml
├── postgres (port 5432)
├── redis (port 6379)
├── orchestrator (port 8000)
└── worker processes
```

### Production Considerations

**Scaling:**
- Worker processes: Additional worker processes can be configured in docker-compose.yml
- Worker concurrency: Increase concurrency per worker process
- Database: Connection pooling

**Monitoring:**
- Health check endpoints
- Task queue depth metrics
- Worker processing latency
- Database query performance

**Security:**
- API key rotation
- Webhook signature validation
- Database credential management
- Network isolation

## Data Models

### eval_runs Table

```sql
CREATE TABLE eval_runs (
    id SERIAL PRIMARY KEY,
    task_id TEXT UNIQUE NOT NULL,
    dataset_path TEXT,
    model TEXT,
    scorers TEXT[],
    status TEXT,
    metrics JSONB,
    created_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

**Metrics JSONB Structure:**
```json
{
  "total": 10,
  "exact_match_rate": 0.8,
  "passed": true,
  "evaluator_pass_rate": 0.9,
  "evaluator_passed_count": 9,
  "evaluator_valid_count": 10,
  "valid_verdict_count": 10,
  "valid_verdict_rate": 1.0,
  "failure_category_counts": {
    "hallucination": 1
  },
  "top_failure_category": "hallucination"
}
```

### eval_samples Table

```sql
CREATE TABLE eval_samples (
    id SERIAL PRIMARY KEY,
    task_id TEXT NOT NULL,
    sample_id TEXT,
    output TEXT,
    expected TEXT,
    scores JSONB,
    eval_result JSONB,
    created_at TIMESTAMP
);
```

**eval_result JSONB Structure:**
```json
{
  "evaluator_name": "llm_judge",
  "passed": false,
  "failure_category": "hallucination",
  "reasoning": "Output incorrectly states Paris is in Germany",
  "error": null
}
```

## Testing Strategy

**Unit Tests:**
- Taxonomy normalization
- Verdict logic
- Schema validation

**Integration Tests:**
- Worker evaluation flow
- Compare logic
- Backward compatibility

**Test Coverage:**
- 99 tests total
- Taxonomy: 16 tests
- Verdict logic: 12 tests
- Compare: 18 tests
- Worker eval: 22 tests

## Future Architecture Considerations

**Planned Enhancements:**
- Multi-tenancy with org/team isolation
- Custom taxonomy per evaluator
- Advanced trend visualization
- Real-time eval execution streaming

**Not Planned:**
- In-UI task submission (keeping clear operational boundaries)
- Public API for sample-level data (security consideration)
- Real-time dashboard updates (read-only polling is sufficient)
