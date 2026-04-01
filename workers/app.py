"""
workers/app.py
Handlers:
  research.stub    — writes shared/docs/{task_id}.md
  dataset.validate — validates JSONL; writes shared/reports/{task_id}_dataset_validation.md
  eval.run         — provider abstraction + Postgres persistence
                     A6 hardening:
                       • inputs.model missing/empty → default anthropic:${DEFAULT_ANTHROPIC_MODEL}
                       • ProviderFatalError (404/401/403) → status=failed, all artifacts written
                       • Telemetry in run.json + DB: elapsed_ms_total, elapsed_ms_avg,
                         retries_count, usage.{input_tokens,output_tokens}, provider
                       • File artifacts always written before DB call
                       • DB failure → task failed, file artifacts kept on disk

All handlers write shared/runs/{task_id}/run.json
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
import redis as redis_lib

sys.path.insert(0, str(Path(__file__).parent.parent))
from schemas.task_protocol import Task, TaskResult, TaskStatus, task_from_json
from providers import resolve_provider
from providers.anthropic import AnthropicProvider, ProviderFatalError
from evals import get_evaluator, EvalInput

REDIS_URL  = os.environ.get("REDIS_URL", "redis://redis:6379/0")
SHARED_DIR = Path(os.environ.get("SHARED_DIR", "/app/shared"))
WORKER_ID  = os.environ.get("WORKER_ID", f"worker-{uuid.uuid4().hex[:6]}")
TASK_QUEUE = "tasks:queue"

_SHARED_RESOLVED = SHARED_DIR.resolve()
_DATASETS_DIR    = _SHARED_RESOLVED / "datasets"

_PG_DSN = (
    f"host={os.environ.get('POSTGRES_HOST', 'postgres')} "
    f"port={os.environ.get('POSTGRES_PORT', '5432')} "
    f"dbname={os.environ.get('POSTGRES_DB', '')} "
    f"user={os.environ.get('POSTGRES_USER', '')} "
    f"password={os.environ.get('POSTGRES_PASSWORD', '')}"
)

# A6: default model when inputs.model is absent or empty
_DEFAULT_ANTHROPIC_MODEL = os.environ.get(
    "DEFAULT_ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"
)
_DEFAULT_MODEL_FULL = f"anthropic:{_DEFAULT_ANTHROPIC_MODEL}"

# Empty telemetry dict returned by stub/non-Anthropic providers
_EMPTY_META: dict[str, Any] = {
    "model": None, "stop_reason": None,
    "input_tokens": None, "output_tokens": None,
    "retries_count": 0, "elapsed_ms": 0,
}


# ─────────────────────────────────────────────────────────────────
# Infra helpers
# ─────────────────────────────────────────────────────────────────

def get_redis() -> redis_lib.Redis:
    return redis_lib.from_url(REDIS_URL, decode_responses=True)


def _get_db_conn():
    return psycopg2.connect(_PG_DSN, cursor_factory=psycopg2.extras.RealDictCursor)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_result(r: redis_lib.Redis, result: TaskResult) -> None:
    r.set(f"tasks:result:{result.task_id}", result.model_dump_json())


def _safe_dataset_path(dataset_rel: str) -> Path:
    if not dataset_rel.startswith("datasets/"):
        raise ValueError(
            f"dataset_path must start with 'datasets/'; got {dataset_rel!r}"
        )
    resolved = (_SHARED_RESOLVED / dataset_rel).resolve()
    if not resolved.is_relative_to(_DATASETS_DIR):
        raise ValueError(
            f"dataset_path resolves outside datasets/: {dataset_rel!r}"
        )
    return resolved


# ─────────────────────────────────────────────────────────────────
# Run log
# ─────────────────────────────────────────────────────────────────

class RunLog:
    def __init__(self, task_id: str) -> None:
        self.task_id       = task_id
        self.received_at:  str | None = None
        self.started_at:   str | None = None
        self.completed_at: str | None = None
        self.transitions:  list[dict] = []
        self.output_path:  str | None = None
        self.error:        str | None = None
        self.worker_id     = WORKER_ID
        self.summary:      dict | None = None

    def record(self, status: str, note: str = "") -> None:
        entry: dict = {"status": status, "at": _now_iso()}
        if note:
            entry["note"] = note
        self.transitions.append(entry)

    def flush(self) -> None:
        run_dir = SHARED_DIR / "runs" / self.task_id
        run_dir.mkdir(parents=True, exist_ok=True)
        payload: dict = {
            "task_id":      self.task_id,
            "worker_id":    self.worker_id,
            "received_at":  self.received_at,
            "started_at":   self.started_at,
            "completed_at": self.completed_at,
            "output_path":  self.output_path,
            "error":        self.error,
            "transitions":  self.transitions,
        }
        if self.summary is not None:
            payload["summary"] = self.summary
        (run_dir / "run.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )


# ─────────────────────────────────────────────────────────────────
# Handler A — research.stub
# ─────────────────────────────────────────────────────────────────

def _write_research_markdown(task: Task) -> Path:
    docs_dir = SHARED_DIR / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    artifact     = docs_dir / f"{task.task_id}.md"
    inputs_block = json.dumps(task.inputs, indent=2, ensure_ascii=False)
    content = f"""# Research Task: {task.description}

## Metadata

| Field      | Value |
|------------|-------|
| task_id    | `{task.task_id}` |
| task_type  | `{task.task_type}` |
| created_at | {task.created_at} |
| worker_id  | {WORKER_ID} |
| started_at | {_now_iso()} |

## Inputs

```json
{inputs_block}
```

## Findings

> **Stub** — automated research not yet implemented.

- [ ] Topic analysis
- [ ] Source gathering
- [ ] Synthesis

---
*Generated by {WORKER_ID}*
"""
    artifact.write_text(content, encoding="utf-8")
    return artifact


def handle_research_stub(
    task: Task, log: RunLog, r: redis_lib.Redis
) -> tuple[TaskStatus, str, str | None]:
    return TaskStatus.done, str(_write_research_markdown(task)), None


# ─────────────────────────────────────────────────────────────────
# Handler B — dataset.validate
# ─────────────────────────────────────────────────────────────────

_REQUIRED_KEYS = {"id", "prompt"}


def _validate_jsonl(file_path: Path) -> dict[str, Any]:
    errors: list[dict] = []
    preview: list[dict] = []
    total = valid = invalid = 0
    with file_path.open("r", encoding="utf-8") as fh:
        for lineno, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line:
                continue
            total += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                invalid += 1
                if len(errors) < 10:
                    errors.append({"line": lineno, "error": f"JSON parse error: {exc}"})
                continue
            if not isinstance(obj, dict):
                invalid += 1
                if len(errors) < 10:
                    errors.append({"line": lineno, "error": "not a JSON object"})
                continue
            line_errors: list[str] = []
            for key in _REQUIRED_KEYS:
                if key not in obj:
                    line_errors.append(f"missing required key '{key}'")
                elif not isinstance(obj[key], str) or not obj[key].strip():
                    line_errors.append(f"'{key}' must be a non-empty string")
            if "expected" in obj and obj["expected"] is not None:
                if not isinstance(obj["expected"], str):
                    line_errors.append("'expected' must be a string or null")
            if "metadata" in obj and obj["metadata"] is not None:
                if not isinstance(obj["metadata"], dict):
                    line_errors.append("'metadata' must be an object or null")
            if line_errors:
                invalid += 1
                if len(errors) < 10:
                    errors.append({"line": lineno, "error": "; ".join(line_errors)})
            else:
                valid += 1
                if len(preview) < 3:
                    preview.append({"line": lineno, "id": obj["id"],
                                    "prompt_snippet": obj["prompt"][:80]})
    return {"total_lines": total, "valid_count": valid, "invalid_count": invalid,
            "error_examples": errors, "sample_preview": preview}


def _write_validation_report(task: Task, stats: dict[str, Any], dataset_path: Path) -> Path:
    reports_dir = SHARED_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{task.task_id}_dataset_validation.md"
    try:
        host_rel = str(dataset_path.relative_to(Path("/app")))
    except ValueError:
        host_rel = str(dataset_path)
    passed       = stats["invalid_count"] == 0
    result_badge = "✅ PASSED" if passed else "⚠️ ISSUES FOUND"
    errors_block = ""
    if stats["error_examples"]:
        rows = "\n".join(f"| {e['line']} | `{e['error']}` |"
                         for e in stats["error_examples"])
        errors_block = f"\n## Errors\n\n| Line | Error |\n|------|-------|\n{rows}\n"
    preview_block = ""
    if stats["sample_preview"]:
        rows = "\n".join(f"| {p['line']} | `{p['id']}` | {p['prompt_snippet']} |"
                         for p in stats["sample_preview"])
        preview_block = (f"\n## Preview\n\n| Line | id | prompt |\n"
                         f"|------|----|--------|\n{rows}\n")
    content = (
        f"# Dataset Validation — {result_badge}\n\n"
        f"| Field | Value |\n|-------|-------|\n"
        f"| task_id | `{task.task_id}` |\n| dataset | `{host_rel}` |\n"
        f"| worker_id | {WORKER_ID} |\n| validated_at | {_now_iso()} |\n\n"
        f"| Metric | Count |\n|--------|-------|\n"
        f"| Total | {stats['total_lines']} |\n| Valid | {stats['valid_count']} |\n"
        f"| Invalid | {stats['invalid_count']} |\n"
        f"{errors_block}{preview_block}\n---\n*Generated by {WORKER_ID}*\n"
    )
    report_path.write_text(content, encoding="utf-8")
    return report_path


def handle_dataset_validate(
    task: Task, log: RunLog, r: redis_lib.Redis
) -> tuple[TaskStatus, str, str | None]:
    dataset_rel = task.inputs.get("dataset_path", "")
    if not dataset_rel:
        raise ValueError("inputs.dataset_path is required for dataset.validate tasks")
    dataset_path = _safe_dataset_path(dataset_rel)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")
    log.record("validating", note=str(dataset_path))
    stats = _validate_jsonl(dataset_path)
    report_path = _write_validation_report(task, stats, dataset_path)
    passed = stats["invalid_count"] == 0
    log.summary = {
        "total_lines": stats["total_lines"], "valid_count": stats["valid_count"],
        "invalid_count": stats["invalid_count"], "passed": passed,
        "report_path": str(report_path),
    }
    log.record("validated",
               note=(f"valid={stats['valid_count']} invalid={stats['invalid_count']}"
                     f" passed={passed}"))
    if passed:
        return TaskStatus.done, str(report_path), None
    return (TaskStatus.failed, str(report_path),
            f"Dataset validation failed: invalid_count={stats['invalid_count']}")


# ─────────────────────────────────────────────────────────────────
# Handler C — eval.run  (A6 hardened)
# ─────────────────────────────────────────────────────────────────

_KNOWN_SCORERS   = {"exact_match", "contains_expected", "format_nonempty"}
_DEFAULT_SCORERS = ["exact_match", "contains_expected", "format_nonempty"]


def _score_sample(scorer: str, output: str, expected: str | None) -> int:
    if scorer == "exact_match":
        return 1 if (expected is not None and output == expected) else 0
    if scorer == "contains_expected":
        return 1 if (expected is not None and expected in output) else 0
    if scorer == "format_nonempty":
        return 1 if output.strip() != "" else 0
    raise ValueError(f"Unknown scorer: {scorer!r}")


def _call_provider(
    provider: Any, prompt: str, expected: str | None
) -> tuple[str, dict[str, Any]]:
    """
    Dispatch to generate_with_meta() (AnthropicProvider) or generate().
    Returns (text, meta_dict).
    ProviderFatalError propagates unchanged — caller breaks the sample loop.
    """
    if isinstance(provider, AnthropicProvider):
        text, meta = provider.generate_with_meta(prompt=prompt)
        return text, meta.to_dict()
    text = provider.generate(prompt=prompt, expected=expected)
    return text, dict(_EMPTY_META)


def _write_eval_report(
    task:            Task,
    dataset_path:    Path,
    model:           str,
    effective_model: str,
    scorers:         list[str],
    metrics:         dict[str, Any],
    failures:        list[dict],
    fallback_note:   str | None,
    error_note:      str | None = None,
) -> Path:
    """Write eval_report.md.  Always called, even on fatal provider error."""
    reports_dir = SHARED_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{task.task_id}_eval_report.md"
    try:
        host_rel = str(dataset_path.relative_to(Path("/app")))
    except ValueError:
        host_rel = str(dataset_path)

    passed       = bool(metrics.get("passed", False))
    if error_note:
        result_badge = "❌ FAILED"
    else:
        result_badge = "✅ PASSED" if passed else "⚠️ NOT PERFECT"

    scorers_list = ", ".join(f"`{s}`" for s in scorers)

    def _fmt(v: Any) -> str:
        return f"{v:.4f}" if isinstance(v, float) else str(v)

    score_rows = "\n".join([
        f"| total                  | {metrics.get('total', 0)} |",
        f"| exact_match_rate       | {_fmt(metrics.get('exact_match_rate', 0.0))} |",
        f"| contains_expected_rate | {_fmt(metrics.get('contains_expected_rate', 0.0))} |",
        f"| nonempty_rate          | {_fmt(metrics.get('nonempty_rate', 0.0))} |",
        f"| passed                 | {'yes' if passed else 'no'} |",
    ])

    telem_rows = ""
    if metrics.get("elapsed_ms_total") is not None:
        telem_rows += f"| elapsed_ms_total       | {metrics['elapsed_ms_total']} |\n"
    if metrics.get("elapsed_ms_avg") is not None:
        telem_rows += f"| elapsed_ms_avg         | {metrics['elapsed_ms_avg']} |\n"
    if metrics.get("retries_count") is not None:
        telem_rows += f"| retries_count          | {metrics['retries_count']} |\n"
    usage = metrics.get("usage") or {}
    if usage.get("input_tokens") is not None:
        telem_rows += f"| usage.input_tokens     | {usage['input_tokens']} |\n"
    if usage.get("output_tokens") is not None:
        telem_rows += f"| usage.output_tokens    | {usage['output_tokens']} |\n"

    failures_block = ""
    if failures:
        rows = "\n".join(
            f"| `{f['sample_id']}` | {str(f.get('expected') or '')[:40]}"
            f" | {str(f.get('output') or '')[:40]} |"
            for f in failures
        )
        failures_block = (
            f"\n## Top Failures (exact_match=0, up to 5)\n\n"
            f"| sample_id | expected | output |\n"
            f"|-----------|----------|--------|\n{rows}\n"
        )

    error_block    = f"\n> ❌ **Provider error:** {error_note}\n" if error_note else ""
    fallback_block = f"\n> ⚠️ **Provider fallback:** {fallback_note}\n" if fallback_note else ""
    model_display  = model if model == effective_model else f"{model} → {effective_model}"

    content = (
        f"# Eval Report — {result_badge}\n\n"
        f"## Metadata\n\n| Field | Value |\n|-------|-------|\n"
        f"| task_id | `{task.task_id}` |\n"
        f"| dataset | `{host_rel}` |\n"
        f"| model | `{model_display}` |\n"
        f"| scorers | {scorers_list} |\n"
        f"| worker_id | {WORKER_ID} |\n"
        f"| evaluated_at | {_now_iso()} |\n"
        f"{error_block}{fallback_block}\n"
        f"## Metrics\n\n| Metric | Value |\n|--------|-------|\n"
        f"{score_rows}\n{telem_rows}"
        f"{failures_block}\n---\n*Generated by {WORKER_ID}*\n"
    )
    report_path.write_text(content, encoding="utf-8")
    return report_path


# ── Postgres persistence ───────────────────────────────────────────

_SQL_UPSERT_RUN = """
    INSERT INTO eval_runs
        (task_id, dataset_path, model, scorers, status, metrics, completed_at)
    VALUES (%(task_id)s, %(dataset_path)s, %(model)s, %(scorers)s,
            %(status)s, %(metrics)s, %(completed_at)s)
    ON CONFLICT (task_id) DO UPDATE SET
        dataset_path = EXCLUDED.dataset_path,
        model        = EXCLUDED.model,
        scorers      = EXCLUDED.scorers,
        status       = EXCLUDED.status,
        metrics      = EXCLUDED.metrics,
        completed_at = EXCLUDED.completed_at
"""

_SQL_UPSERT_SAMPLE = """
    INSERT INTO eval_samples
        (task_id, sample_id, prompt, expected, output, scores)
    VALUES (%(task_id)s, %(sample_id)s, %(prompt)s, %(expected)s,
            %(output)s, %(scores)s)
    ON CONFLICT (task_id, sample_id) DO UPDATE SET
        prompt   = EXCLUDED.prompt,
        expected = EXCLUDED.expected,
        output   = EXCLUDED.output,
        scores   = EXCLUDED.scores
"""


def _pg_persist_eval(
    *,
    task_id:      str,
    dataset_path: str,
    model:        str,
    scorers:      list[str],
    status:       str,
    metrics:      dict[str, Any],
    completed_at: str,
    samples:      list[dict],
) -> None:
    conn = _get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(_SQL_UPSERT_RUN, {
                "task_id":      task_id,
                "dataset_path": dataset_path,
                "model":        model,
                "scorers":      json.dumps(scorers),
                "status":       status,
                "metrics":      json.dumps(metrics),
                "completed_at": completed_at,
            })
            for s in samples:
                cur.execute(_SQL_UPSERT_SAMPLE, {
                    "task_id":   task_id,
                    "sample_id": s["sample_id"],
                    "prompt":    s["prompt"],
                    "expected":  s.get("expected"),
                    "output":    s["output"],
                    "scores":    json.dumps(s["scores"]),
                })
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def handle_eval_run(
    task: Task, log: RunLog, r: redis_lib.Redis
) -> tuple[TaskStatus, str, str | None]:

    # ── 1. Validate + default inputs ──────────────────────────────
    dataset_rel = task.inputs.get("dataset_path", "")
    if not dataset_rel:
        raise ValueError("inputs.dataset_path is required")

    raw_model       = (task.inputs.get("model") or "").strip()
    requested_model = raw_model if raw_model else _DEFAULT_MODEL_FULL

    scorers = task.inputs.get("scorers", list(_DEFAULT_SCORERS))
    if not isinstance(scorers, list) or not scorers:
        raise ValueError("inputs.scorers must be a non-empty list")
    unknown = set(scorers) - _KNOWN_SCORERS
    if unknown:
        raise ValueError(
            f"Unknown scorers: {sorted(unknown)}. Known: {sorted(_KNOWN_SCORERS)}"
        )

    dataset_path = _safe_dataset_path(dataset_rel)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    if not raw_model:
        log.record(
            "model_defaulted",
            note=f"inputs.model empty; using default {requested_model!r}",
        )
        print(f"[{WORKER_ID}] model defaulted to {requested_model!r}", flush=True)

    # ── 2. Resolve provider ───────────────────────────────────────
    provider, fallback_reason = resolve_provider(requested_model)
    effective_model           = type(provider).__name__

    if fallback_reason:
        log.record("provider_fallback", note=fallback_reason)
        print(f"[{WORKER_ID}] provider_fallback: {fallback_reason}", flush=True)

    # ── 2b. Select evaluator ──────────────────────────────────────
    # Check if inputs specify evaluator; default to deterministic
    evaluator_name = task.inputs.get("evaluator", "deterministic")
    use_llm_judge  = (evaluator_name == "llm_judge")
    
    if use_llm_judge:
        judge_model = task.inputs.get("judge_model", "anthropic:claude-sonnet-4-5-20250929")
        evaluator = get_evaluator("llm_judge", judge_model=judge_model)
        log.record("evaluator_selected", note=f"llm_judge with model {judge_model}")
        print(f"[{WORKER_ID}] using LLM judge: {judge_model}", flush=True)
    else:
        evaluator = get_evaluator("deterministic", scorers=scorers)
        log.record("evaluator_selected", note=f"deterministic with scorers {scorers}")
        print(f"[{WORKER_ID}] using deterministic scorers: {scorers}", flush=True)

    # ── 3. Prepare output paths ───────────────────────────────────
    run_dir = SHARED_DIR / "runs" / task.task_id
    run_dir.mkdir(parents=True, exist_ok=True)
    results_path = run_dir / "eval_results.jsonl"

    log.record("evaluating", note=str(dataset_path))

    # ── 4. Score loop ─────────────────────────────────────────────
    totals: dict[str, int] = {s: 0 for s in scorers}
    total_rows   = 0
    failures:    list[dict] = []
    all_samples: list[dict] = []

    # A6 telemetry accumulators
    acc_input_tokens:  int | None = None
    acc_output_tokens: int | None = None
    acc_retries:       int        = 0
    acc_provider_ms:   int        = 0   # sum of per-sample provider elapsed_ms
    fatal_error:       str | None = None
    
    # Evaluator verdict tracking (for llm_judge runs)
    evaluator_passed_count: int = 0  # Samples with passed=True
    evaluator_valid_count:  int = 0  # Samples with valid verdict (True or False)
    
    wall_start = time.monotonic()

    with dataset_path.open("r", encoding="utf-8") as fh, \
         results_path.open("w", encoding="utf-8") as out:

        for raw_line in fh:
            line = raw_line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue

            sample_id = str(row.get("id", ""))
            prompt    = str(row.get("prompt", ""))
            expected: str | None = row.get("expected")
            if isinstance(expected, str) and not expected.strip():
                expected = None

            # Call provider — ProviderFatalError aborts the loop
            try:
                output, meta_d = _call_provider(provider, prompt, expected)
            except ProviderFatalError as exc:
                fatal_error = str(exc)
                log.record("provider_fatal", note=fatal_error)
                print(f"[{WORKER_ID}] ProviderFatalError: {fatal_error}", flush=True)
                break

            # Accumulate telemetry
            sample_ms = meta_d.get("elapsed_ms") or 0
            acc_provider_ms += sample_ms
            if meta_d.get("input_tokens") is not None:
                acc_input_tokens  = (acc_input_tokens  or 0) + meta_d["input_tokens"]
            if meta_d.get("output_tokens") is not None:
                acc_output_tokens = (acc_output_tokens or 0) + meta_d["output_tokens"]
            acc_retries += meta_d.get("retries_count") or 0

            # ── Run evaluator ─────────────────────────────────────────
            eval_input = EvalInput(
                task_id=task.task_id,
                dataset_item_id=sample_id,
                prompt=prompt,
                expected_answer=expected,
                model_output=output,
                task_type=task.task_type,
                metadata=row.get("metadata", {}),
                rubric=None,  # Use default rubric for now
            )
            
            eval_result = evaluator.evaluate(eval_input)
            
            # Track evaluator verdicts for run-level aggregation
            # For judge runs: must have valid verdict on EVERY sample
            if eval_result.passed is not None:
                evaluator_valid_count += 1
                if eval_result.passed:
                    evaluator_passed_count += 1
            
            # Extract scores for backward compatibility with existing dashboards
            # Deterministic evaluator returns scores in metrics dict
            # LLM judge needs to be converted to legacy format
            if use_llm_judge:
                # For LLM judge, preserve deterministic scores for compatibility
                # and add eval_result structure
                scores: dict[str, int] = {}
                for scorer in scorers:
                    scores[scorer] = _score_sample(scorer, output, expected)
                    totals[scorer] += scores[scorer]
            else:
                # Deterministic evaluator already has scores in metrics
                scores = eval_result.metrics.copy()
                for scorer in scorers:
                    totals[scorer] += scores.get(scorer, 0)

            total_rows += 1
            sample_record: dict = {
                "sample_id":  sample_id,
                "prompt":     prompt,
                "expected":   expected,
                "output":     output,
                "scores":     scores,
                "elapsed_ms": sample_ms,
            }
            
            # Attach structured eval_result for new capabilities
            if use_llm_judge or eval_result.error:
                sample_record["eval_result"] = {
                    "evaluator_name":    eval_result.evaluator_name,
                    "score":             eval_result.score,
                    "passed":            eval_result.passed,
                    "confidence":        eval_result.confidence,
                    "failure_category":  eval_result.failure_category,
                    "summary_reason":    eval_result.summary_reason,
                    "rubric_scores":     [rs.model_dump() for rs in eval_result.rubric_scores],
                    "error":             eval_result.error,
                }
                if eval_result.raw_judge_output:
                    sample_record["eval_result"]["raw_judge_output"] = eval_result.raw_judge_output
            
            # Attach non-null provider meta to each sample
            provider_meta = {k: v for k, v in meta_d.items() if v is not None}
            if provider_meta:
                sample_record["provider_meta"] = provider_meta

            all_samples.append(sample_record)
            out.write(json.dumps(sample_record, ensure_ascii=False) + "\n")

            if scores.get("exact_match", 0) == 0 and len(failures) < 5:
                failures.append({"sample_id": sample_id,
                                  "expected":  expected,
                                  "output":    output})

    total_wall_ms = int((time.monotonic() - wall_start) * 1000)

    # ── 5. Aggregate metrics ──────────────────────────────────────
    def _rate(s: str) -> float:
        return round(totals[s] / total_rows, 4) if total_rows > 0 else 0.0

    em_rate  = _rate("exact_match")       if "exact_match"       in scorers else None
    ce_rate  = _rate("contains_expected") if "contains_expected" in scorers else None
    nne_rate = _rate("format_nonempty")   if "format_nonempty"   in scorers else None
    
    # Run-level pass/fail: use evaluator verdict for judge runs, deterministic for others
    if use_llm_judge:
        # LLM judge: ALL samples must have valid verdicts AND all must pass
        if total_rows == 0:
            # Empty run: no samples evaluated, cannot pass
            passed = False
            evaluator_pass_rate = 0.0
        elif evaluator_valid_count != total_rows:
            # Some samples lack valid verdict (error/timeout/parsing failure)
            passed = False
            evaluator_pass_rate = (
                round(evaluator_passed_count / total_rows, 4) if total_rows > 0 else 0.0
            )
        elif evaluator_passed_count != total_rows:
            # All samples have verdicts, but some failed
            passed = False
            evaluator_pass_rate = round(evaluator_passed_count / total_rows, 4)
        else:
            # All samples have valid verdicts and all passed
            passed = not fatal_error
            evaluator_pass_rate = 1.0
    else:
        # Deterministic: legacy exact_match aggregation
        passed = (em_rate == 1.0) if (em_rate is not None and not fatal_error) else False
        evaluator_pass_rate = None

    elapsed_ms_avg = (
        round(acc_provider_ms / total_rows) if total_rows > 0 else 0
    )

    metrics: dict[str, Any] = {
        # scoring
        "total":                  total_rows,
        "exact_match_rate":       em_rate,
        "contains_expected_rate": ce_rate,
        "nonempty_rate":          nne_rate,
        "passed":                 passed,
        # evaluator verdicts (llm_judge runs)
        "evaluator_pass_rate":    evaluator_pass_rate,
        "evaluator_passed_count": evaluator_passed_count if use_llm_judge else None,
        "evaluator_valid_count":  evaluator_valid_count if use_llm_judge else None,
        # A6 telemetry — persisted in eval_runs.metrics JSONB
        "elapsed_ms_total":       total_wall_ms,
        "elapsed_ms_avg":         elapsed_ms_avg,
        "retries_count":          acc_retries,
        "provider":               effective_model,
        "usage": {
            "input_tokens":  acc_input_tokens,
            "output_tokens": acc_output_tokens,
        },
    }

    # ── 6. Write file artifacts (always, even on fatal error) ─────
    report_path = _write_eval_report(
        task            = task,
        dataset_path    = dataset_path,
        model           = requested_model,
        effective_model = effective_model,
        scorers         = scorers,
        metrics         = metrics,
        failures        = failures,
        fallback_note   = fallback_reason,
        error_note      = fatal_error,
    )
    completed_at = _now_iso()

    log.summary = {
        "requested_model":   requested_model,
        "effective_model":   effective_model,
        "provider_fallback": fallback_reason,
        "fatal_error":       fatal_error,
        "metrics":           metrics,
        "results_path":      str(results_path),
        "report_path":       str(report_path),
        "passed":            passed,
    }
    log.record(
        "evaluated",
        note=(
            f"total={total_rows} em={em_rate} passed={passed} "
            f"elapsed_ms_total={total_wall_ms} elapsed_ms_avg={elapsed_ms_avg} "
            f"retries={acc_retries} "
            f"in_tok={acc_input_tokens} out_tok={acc_output_tokens}"
        ),
    )

    # ── 7. Postgres persistence ───────────────────────────────────
    db_status = "failed" if fatal_error else "done"
    try:
        _pg_persist_eval(
            task_id      = task.task_id,
            dataset_path = dataset_rel,
            model        = requested_model,
            scorers      = scorers,
            status       = db_status,
            metrics      = metrics,
            completed_at = completed_at,
            samples      = all_samples,
        )
        log.record(
            "db_persisted",
            note=f"eval_runs({db_status}) + {len(all_samples)} eval_samples",
        )
        print(
            f"[{WORKER_ID}] db_persisted {task.task_id} "
            f"status={db_status} samples={len(all_samples)}",
            flush=True,
        )
    except Exception as db_exc:
        err = f"DB persistence failed: {db_exc}"
        log.record("db_failed", note=err)
        print(f"[{WORKER_ID}] {err}", flush=True)
        raise RuntimeError(err) from db_exc

    # ── 8. Return ─────────────────────────────────────────────────
    if fatal_error:
        return (
            TaskStatus.failed,
            str(report_path),
            f"Provider fatal error: {fatal_error}",
        )
    return TaskStatus.done, str(report_path), None


# ─────────────────────────────────────────────────────────────────
# Router
# ─────────────────────────────────────────────────────────────────

HANDLERS = {
    "research.stub":    handle_research_stub,
    "dataset.validate": handle_dataset_validate,
    "eval.run":         handle_eval_run,
}


def process(raw: str, r: redis_lib.Redis) -> None:
    task = task_from_json(raw)
    log  = RunLog(task.task_id)
    log.received_at = _now_iso()
    log.record("received")
    print(f"[{WORKER_ID}] received {task.task_id} type={task.task_type}", flush=True)

    log.started_at = _now_iso()
    log.record("running")
    _write_result(r, TaskResult(task_id=task.task_id, status=TaskStatus.running))

    handler = HANDLERS.get(task.task_type)
    try:
        if handler is None:
            raise ValueError(
                f"Unknown task_type: {task.task_type!r}. Known: {list(HANDLERS)}"
            )
        final_status, output_path, error = handler(task, log, r)
        log.completed_at = _now_iso()
        log.output_path  = output_path
        log.error        = error
        log.record(final_status.value, note=output_path)
        _write_result(r, TaskResult(
            task_id=task.task_id, status=final_status,
            output_path=output_path, error=error, completed_at=log.completed_at,
        ))
        print(
            f"[{WORKER_ID}] {final_status.value} {task.task_id} -> {output_path}",
            flush=True,
        )
    except Exception as exc:
        log.completed_at = _now_iso()
        log.error = str(exc)
        log.record("failed", note=str(exc))
        _write_result(r, TaskResult(
            task_id=task.task_id, status=TaskStatus.failed,
            error=str(exc), completed_at=log.completed_at,
        ))
        print(f"[{WORKER_ID}] FAILED {task.task_id}: {exc}", flush=True)
    finally:
        try:
            log.flush()
        except Exception as log_exc:
            print(f"[{WORKER_ID}] WARNING: run.json flush failed: {log_exc}", flush=True)


def main() -> None:
    print(f"[{WORKER_ID}] starting — queue={TASK_QUEUE} shared={SHARED_DIR}", flush=True)
    print(f"[{WORKER_ID}] default model: {_DEFAULT_MODEL_FULL!r}", flush=True)
    print(f"[{WORKER_ID}] registered handlers: {list(HANDLERS)}", flush=True)
    while True:
        try:
            r    = get_redis()
            item = r.brpop(TASK_QUEUE, timeout=5)
            if item:
                _, raw = item
                process(raw, r)
        except redis_lib.exceptions.ConnectionError as exc:
            print(f"[{WORKER_ID}] Redis error: {exc} — retry in 3s", flush=True)
            time.sleep(3)
        except Exception as exc:
            print(f"[{WORKER_ID}] loop error: {exc} — retry in 3s", flush=True)
            time.sleep(3)


if __name__ == "__main__":
    main()
