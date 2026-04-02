"""
orchestrator/app.py  v1.8.0
A9 additive patch — dashboard UI on top of A7 (v1.7.0).

Changes from v1.7.0
───────────────────
• Added at TOP of file (imports only):
    import math
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates

• Mounted AFTER app = FastAPI(...):
    app.mount("/static", ...)
    templates = Jinja2Templates(...)

• Two NEW routes appended at end of file:
    GET /dashboard
    GET /dashboard/run/{task_id}

• Two NEW helper functions (dashboard-only):
    _last_nightly_summary()
    _distinct_models()

EVERYTHING ELSE IS IDENTICAL TO v1.7.0:
    All existing routes, helpers, Pydantic models,
    DB helpers, query builders — character-for-character preserved.
    GET /             ← unchanged
    GET /health       ← unchanged
    GET /schemas      ← unchanged
    POST /task/submit ← unchanged
    GET /task/status  ← unchanged
    GET /eval/runs    ← unchanged
    GET /eval/run/{id}            ← unchanged
    GET /eval/run/{id}/samples    ← unchanged
"""

from __future__ import annotations

import json
import math
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras
import redis as redis_lib
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent))
from schemas.task_protocol import (
    Task, TaskResult, TaskStatus,
    result_from_json,
)

REDIS_URL  = os.environ.get("REDIS_URL", "redis://redis:6379/0")
TASK_QUEUE = "tasks:queue"

_PG_DSN = (
    f"host={os.environ.get('POSTGRES_HOST', 'postgres')} "
    f"port={os.environ.get('POSTGRES_PORT', '5432')} "
    f"dbname={os.environ.get('POSTGRES_DB', '')} "
    f"user={os.environ.get('POSTGRES_USER', '')} "
    f"password={os.environ.get('POSTGRES_PASSWORD', '')}"
)

SHARED_DIR = Path(os.environ.get("SHARED_DIR", "/app/shared"))


# ─────────────────────────────────────────────────────────────────
# Connection helpers  (unchanged from A7)
# ─────────────────────────────────────────────────────────────────

def get_redis() -> redis_lib.Redis:
    return redis_lib.from_url(REDIS_URL, decode_responses=True)


def _get_db_conn():
    """Open a fresh psycopg2 connection. Caller must close."""
    return psycopg2.connect(_PG_DSN, cursor_factory=psycopg2.extras.RealDictCursor)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────
# Pydantic response models  (unchanged from A7)
# ─────────────────────────────────────────────────────────────────

class EvalRunRow(BaseModel):
    task_id:       str
    dataset_path:  str
    model:         str
    scorers:       List[str]
    status:        str
    metrics:       Optional[Dict[str, Any]] = None
    created_at:    Optional[str]            = None
    completed_at:  Optional[str]            = None
    # Augmented fields (from run.json, present only on GET /eval/run/{id})
    report_path:   Optional[str]            = None
    results_path:  Optional[str]            = None


class EvalRunsResponse(BaseModel):
    runs:   List[EvalRunRow]
    count:  int   = Field(description="Number of rows in this page")
    total:  int   = Field(description="Total matching rows (before pagination)")
    limit:  int
    offset: int


class EvalSampleRow(BaseModel):
    task_id:    str
    sample_id:  str
    prompt:     str
    expected:   Optional[str] = None
    output:     str
    scores:     Optional[Dict[str, Any]] = None


class EvalSamplesResponse(BaseModel):
    task_id:  str
    samples:  List[EvalSampleRow]
    count:    int   = Field(description="Number of rows in this page")
    total:    int   = Field(description="Total matching rows (before pagination)")
    limit:    int
    offset:   int


# ─────────────────────────────────────────────────────────────────
# DB coercion helpers  (unchanged from A7)
# ─────────────────────────────────────────────────────────────────

def _coerce_run_row(row: Any) -> dict:
    """Convert RealDictRow → plain JSON-serialisable dict for EvalRunRow."""
    d = dict(row)
    for col in ("scorers", "metrics"):
        if isinstance(d.get(col), str):
            d[col] = json.loads(d[col])
    for col in ("created_at", "completed_at"):
        v = d.get(col)
        if v is not None and hasattr(v, "isoformat"):
            d[col] = v.isoformat()
    return d


def _coerce_sample_row(row: Any) -> dict:
    d = dict(row)
    if isinstance(d.get("scores"), str):
        d["scores"] = json.loads(d["scores"])
    return d


def _artifact_paths(task_id: str) -> dict:
    """
    Read shared/runs/{task_id}/run.json and extract artifact paths from summary.
    Returns {report_path: str|None, results_path: str|None}.
    Never raises.
    """
    run_json = SHARED_DIR / "runs" / task_id / "run.json"
    try:
        data    = json.loads(run_json.read_text(encoding="utf-8"))
        summary = data.get("summary") or {}
        return {
            "report_path":  summary.get("report_path"),
            "results_path": summary.get("results_path"),
        }
    except Exception:
        return {"report_path": None, "results_path": None}


# ─────────────────────────────────────────────────────────────────
# Query builders  (unchanged from A7)
# safe parameterized SQL — zero string interpolation of user input
# ─────────────────────────────────────────────────────────────────

_ALLOWED_SORT   = {"created_at", "completed_at"}
_ALLOWED_ORDER  = {"asc", "desc"}
_ALLOWED_STATUS = {"done", "failed", "running", "queued"}


def _build_runs_query(
    *,
    status:   str | None,
    model:    str | None,
    provider: str | None,
    passed:   bool | None,
    since:    str | None,
    until:    str | None,
    sort:     str,
    order:    str,
    limit:    int,
    offset:   int,
) -> tuple[str, str, list, list]:
    sort_col = sort  if sort  in _ALLOWED_SORT  else "created_at"
    ord_dir  = order if order in _ALLOWED_ORDER else "desc"

    where_clauses: list[str] = []
    params:        list      = []

    if status:
        where_clauses.append("status = %s")
        params.append(status)

    if model:
        where_clauses.append("model = %s")
        params.append(model)

    if provider:
        where_clauses.append("metrics->>'provider' ILIKE %s")
        params.append(f"%{provider}%")

    if passed is not None:
        where_clauses.append("(metrics->>'passed')::boolean = %s")
        params.append(passed)

    if since:
        where_clauses.append("COALESCE(completed_at, created_at) >= %s::timestamptz")
        params.append(since)

    if until:
        where_clauses.append("COALESCE(completed_at, created_at) <= %s::timestamptz")
        params.append(until)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    data_sql = f"""
        SELECT task_id, dataset_path, model, scorers, status, metrics,
               created_at, completed_at
        FROM   eval_runs
        {where_sql}
        ORDER  BY COALESCE({sort_col}, created_at) {ord_dir}
        LIMIT  %s OFFSET %s
    """
    count_sql = f"SELECT COUNT(*) FROM eval_runs {where_sql}"

    data_params  = list(params) + [limit, offset]
    count_params = list(params)

    return data_sql, count_sql, data_params, count_params


def _build_samples_query(
    *,
    task_id:   str,
    sample_id: str | None,
    q:         str | None,
    limit:     int,
    offset:    int,
) -> tuple[str, str, list, list]:
    where_clauses: list[str] = ["task_id = %s"]
    params:        list      = [task_id]

    if sample_id:
        where_clauses.append("sample_id = %s")
        params.append(sample_id)

    if q:
        where_clauses.append(
            "(prompt ILIKE %s OR expected ILIKE %s OR output ILIKE %s)"
        )
        like = f"%{q}%"
        params.extend([like, like, like])

    where_sql = "WHERE " + " AND ".join(where_clauses)

    data_sql = f"""
        SELECT task_id, sample_id, prompt, expected, output, scores
        FROM   eval_samples
        {where_sql}
        ORDER  BY sample_id
        LIMIT  %s OFFSET %s
    """
    count_sql = f"SELECT COUNT(*) FROM eval_samples {where_sql}"

    data_params  = list(params) + [limit, offset]
    count_params = list(params)

    return data_sql, count_sql, data_params, count_params


# ─────────────────────────────────────────────────────────────────
# DB execution helpers  (unchanged from A7)
# ─────────────────────────────────────────────────────────────────

def _exec_query(sql: str, params: list) -> list[dict]:
    conn = _get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _exec_count(sql: str, params: list) -> int:
    conn = _get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return int(row["count"]) if row else 0
    finally:
        conn.close()


def _check_run_exists(task_id: str) -> bool:
    conn = _get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM eval_runs WHERE task_id = %s", (task_id,))
            return cur.fetchone() is not None
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────
# FastAPI app  (title / version bump only; mounts added for A9)
# ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "AI Worker Orchestrator",
    version     = "1.8.0",
    description = "Orchestrator for AI eval tasks. A9 adds dashboard UI.",
)

# ── A9: static files + templates ─────────────────────────────────
_HERE       = Path(__file__).parent
_STATIC_DIR = _HERE / "static"
_TMPL_DIR   = _HERE / "templates"

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(_TMPL_DIR))


# ─────────────────────────────────────────────────────────────────
# Existing endpoints — UNCHANGED from A7
# ─────────────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


@app.get("/", tags=["meta"])
def root():
    return {"service": "orchestrator", "version": "1.8.0"}


@app.get("/schemas", tags=["meta"])
def get_schemas():
    return {
        "task_schema":        Task.model_json_schema(),
        "task_result_schema": TaskResult.model_json_schema(),
    }


class SubmitRequest(BaseModel):
    description: str
    task_type:   str             = "research.stub"
    inputs:      Dict[str, Any]  = Field(default_factory=dict)
    task_id:     Optional[str]   = None


@app.post("/task/submit", status_code=202, tags=["tasks"])
def submit_task(req: SubmitRequest):
    task = Task(
        task_id     = req.task_id or str(uuid.uuid4()),
        description = req.description,
        task_type   = req.task_type,
        inputs      = req.inputs,
        created_at  = _now_iso(),
        status      = TaskStatus.queued,
    )
    get_redis().lpush(TASK_QUEUE, task.model_dump_json())
    return {
        "task_id":   task.task_id,
        "status":    task.status,
        "task_type": task.task_type,
    }


@app.get("/task/status/{task_id}", tags=["tasks"])
def task_status(task_id: str):
    raw = get_redis().get(f"tasks:result:{task_id}")
    if raw is None:
        return TaskResult(task_id=task_id, status=TaskStatus.queued)
    return result_from_json(raw)


# ── A7: GET /eval/runs ────────────────────────────────────────────

@app.get(
    "/eval/runs",
    response_model = EvalRunsResponse,
    tags           = ["eval"],
    summary        = "List eval runs with filters and pagination",
)
def list_eval_runs(
    limit:    int           = Query(default=20,    ge=1, le=100,
                                    description="Max rows to return (1–100)"),
    offset:   int           = Query(default=0,     ge=0,
                                    description="Row offset for pagination"),
    status:   Optional[str] = Query(default=None,
                                    description="Exact status filter: done|failed|running|queued"),
    model:    Optional[str] = Query(default=None,
                                    description="Exact model string filter"),
    provider: Optional[str] = Query(default=None,
                                    description="Substring match in metrics.provider"),
    passed:   Optional[bool]= Query(default=None,
                                    description="Filter by metrics.passed true/false"),
    since:    Optional[str] = Query(default=None,
                                    description="ISO8601 lower bound on completed_at (or created_at)"),
    until:    Optional[str] = Query(default=None,
                                    description="ISO8601 upper bound on completed_at (or created_at)"),
    sort:     str           = Query(default="created_at",
                                    description="Sort column: created_at|completed_at"),
    order:    str           = Query(default="desc",
                                    description="Sort direction: asc|desc"),
):
    if status and status not in _ALLOWED_STATUS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status {status!r}. Allowed: {sorted(_ALLOWED_STATUS)}",
        )

    data_sql, count_sql, data_params, count_params = _build_runs_query(
        status   = status,
        model    = model,
        provider = provider,
        passed   = passed,
        since    = since,
        until    = until,
        sort     = sort,
        order    = order,
        limit    = limit,
        offset   = offset,
    )

    try:
        raw_rows = _exec_query(data_sql, data_params)
        total    = _exec_count(count_sql, count_params)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database error: {exc}")

    runs = [EvalRunRow(**_coerce_run_row(r)) for r in raw_rows]
    return EvalRunsResponse(
        runs   = runs,
        count  = len(runs),
        total  = total,
        limit  = limit,
        offset = offset,
    )


# ── A7: GET /eval/run/{task_id} ───────────────────────────────────

@app.get(
    "/eval/run/{task_id}",
    response_model = EvalRunRow,
    tags           = ["eval"],
    summary        = "Get a single eval run by task_id (includes artifact paths)",
)
def get_eval_run(task_id: str):
    sql = """
        SELECT task_id, dataset_path, model, scorers, status, metrics,
               created_at, completed_at
        FROM   eval_runs
        WHERE  task_id = %s
    """
    try:
        rows = _exec_query(sql, [task_id])
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database error: {exc}")

    if not rows:
        raise HTTPException(status_code=404, detail=f"eval run {task_id!r} not found")

    d = _coerce_run_row(rows[0])
    d.update(_artifact_paths(task_id))
    return EvalRunRow(**d)


# ── A7: GET /eval/run/{task_id}/samples ──────────────────────────

@app.get(
    "/eval/run/{task_id}/samples",
    response_model = EvalSamplesResponse,
    tags           = ["eval"],
    summary        = "List samples for an eval run with pagination and search",
)
def get_eval_samples(
    task_id:   str,
    limit:     int           = Query(default=20,  ge=1,  le=500,
                                     description="Max rows to return (1–500)"),
    offset:    int           = Query(default=0,   ge=0,
                                     description="Row offset for pagination"),
    sample_id: Optional[str] = Query(default=None,
                                     description="Exact sample_id filter"),
    q:         Optional[str] = Query(default=None,
                                     description="Substring search in prompt / expected / output"),
):
    try:
        if not _check_run_exists(task_id):
            raise HTTPException(
                status_code=404,
                detail=f"eval run {task_id!r} not found",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database error: {exc}")

    data_sql, count_sql, data_params, count_params = _build_samples_query(
        task_id   = task_id,
        sample_id = sample_id,
        q         = q,
        limit     = limit,
        offset    = offset,
    )

    try:
        raw_rows = _exec_query(data_sql, data_params)
        total    = _exec_count(count_sql, count_params)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database error: {exc}")

    samples = [EvalSampleRow(**_coerce_sample_row(r)) for r in raw_rows]
    return EvalSamplesResponse(
        task_id = task_id,
        samples = samples,
        count   = len(samples),
        total   = total,
        limit   = limit,
        offset  = offset,
    )


# ═════════════════════════════════════════════════════════════════
# A9  —  Dashboard (NEW; nothing above changed)
# ═════════════════════════════════════════════════════════════════

_DASH_PAGE_SIZE    = 20
_SAMPLES_PAGE_SIZE = 25


def _last_nightly_summary() -> dict:
    """
    Cheaply fetch the most recent terminal eval run for the nightly badge.
    Returns a dict the template can render; never raises.
    """
    try:
        rows = _exec_query(
            """
            SELECT task_id, status, metrics, completed_at
            FROM   eval_runs
            WHERE  status IN ('done', 'failed')
            ORDER  BY COALESCE(completed_at, created_at) DESC
            LIMIT  1
            """,
            [],
        )
        if not rows:
            return {"available": False}
        row     = _coerce_run_row(rows[0])
        metrics = row.get("metrics") or {}
        return {
            "available":        True,
            "task_id":          row["task_id"],
            "status":           row["status"],
            "completed_at":     row.get("completed_at"),
            "exact_match_rate": metrics.get("exact_match_rate"),
            "nonempty_rate":    metrics.get("nonempty_rate"),
            "elapsed_ms_total": metrics.get("elapsed_ms_total"),
            "model":            metrics.get("provider") or row.get("model"),
        }
    except Exception:
        return {"available": False}


def _distinct_models() -> list[str]:
    """Distinct model strings for the filter dropdown; never raises."""
    try:
        rows = _exec_query(
            "SELECT DISTINCT model FROM eval_runs "
            "WHERE model IS NOT NULL ORDER BY model",
            [],
        )
        return [r["model"] for r in rows]
    except Exception:
        return []


@app.get("/dashboard", response_class=HTMLResponse, tags=["dashboard"])
def dashboard(
    request:  Request,
    page:     int           = Query(1, ge=1),
    status:   Optional[str] = None,
    model:    Optional[str] = None,
    provider: Optional[str] = None,
    passed:   Optional[bool]= None,
):
    """Paginated runs table with filter bar."""
    if status and status not in _ALLOWED_STATUS:
        status = None

    limit  = _DASH_PAGE_SIZE
    offset = (page - 1) * limit

    data_sql, count_sql, data_params, count_params = _build_runs_query(
        status=status, model=model, provider=provider, passed=passed,
        since=None, until=None,
        sort="created_at", order="desc",
        limit=limit, offset=offset,
    )
    runs  = [_coerce_run_row(r) for r in _exec_query(data_sql, data_params)]
    total = _exec_count(count_sql, count_params)
    pages = max(1, math.ceil(total / limit))

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request":    request,
            "runs":       runs,
            "total":      total,
            "page":       page,
            "pages":      pages,
            "page_size":  limit,
            "f_status":   status   or "",
            "f_model":    model    or "",
            "f_provider": provider or "",
            "f_passed":   "" if passed is None else ("true" if passed else "false"),
            "statuses":   sorted(_ALLOWED_STATUS),
            "models":     _distinct_models(),
            "nightly":    _last_nightly_summary(),
        },
    )


@app.get("/dashboard/run/{task_id}", response_class=HTMLResponse, tags=["dashboard"])
def dashboard_run(
    request:      Request,
    task_id:      str,
    samples_page: int           = Query(1, ge=1),
    q:            Optional[str] = None,
):
    """Run detail page — metrics + samples table with search."""
    if not _check_run_exists(task_id):
        raise HTTPException(404, detail="run not found")

    rows = _exec_query(
        """
        SELECT task_id, dataset_path, model, scorers, status, metrics,
               created_at, completed_at
        FROM   eval_runs WHERE task_id = %s
        """,
        [task_id],
    )
    run = _coerce_run_row(rows[0])
    run["report_path"], run["results_path"] = (
        _artifact_paths(task_id)["report_path"],
        _artifact_paths(task_id)["results_path"],
    )

    limit  = _SAMPLES_PAGE_SIZE
    offset = (samples_page - 1) * limit

    data_sql, count_sql, data_params, count_params = _build_samples_query(
        task_id=task_id, sample_id=None, q=q, limit=limit, offset=offset,
    )
    samples       = [_coerce_run_row(r) for r in _exec_query(data_sql, data_params)]
    samples_total = _exec_count(count_sql, count_params)
    samples_pages = max(1, math.ceil(samples_total / limit))

    metrics = run.get("metrics") or {}

    return templates.TemplateResponse(
        "run_detail.html",
        {
            "request":       request,
            "run":           run,
            "metrics":       metrics,
            "samples":       samples,
            "samples_total": samples_total,
            "samples_page":  samples_page,
            "samples_pages": samples_pages,
            "q":             q or "",
            "nightly":       _last_nightly_summary(),
        },
    )


# ═════════════════════════════════════════════════════════════════
# A11  —  Compare runs  (NEW; nothing above changed)
# ═════════════════════════════════════════════════════════════════

def _fetch_run_for_compare(task_id: str) -> dict | None:
    """
    Fetch a single eval_run row + coerce it.
    Returns None if not found. Never raises.
    """
    try:
        rows = _exec_query(
            """
            SELECT task_id, dataset_path, model, scorers, status, metrics,
                   created_at, completed_at
            FROM   eval_runs
            WHERE  task_id = %s
            """,
            [task_id],
        )
        if not rows:
            return None
        return _coerce_run_row(rows[0])
    except Exception:
        return None


def _compare_runs(left: dict, right: dict) -> dict:
    """
    Derive the comparison summary between two coerced run rows.
    All fields safe — missing metrics fall back to None.
    """
    lm = left.get("metrics") or {}
    rm = right.get("metrics") or {}

    l_em  = lm.get("exact_match_rate")
    r_em  = rm.get("exact_match_rate")
    l_pas = lm.get("passed")
    r_pas = rm.get("passed")

    # EM delta
    em_delta: float | None = None
    if l_em is not None and r_em is not None:
        em_delta = round(r_em - l_em, 4)

    # Regression / Improvement / No change verdict
    verdict = "no_change"
    if em_delta is not None:
        if em_delta < -0.0001:
            verdict = "regression"
        elif em_delta > 0.0001:
            verdict = "improvement"
    
    # Sprint 3B: Taxonomy and verdict metrics
    l_top_fail = lm.get("top_failure_category")
    r_top_fail = rm.get("top_failure_category")
    l_judge_rate = lm.get("evaluator_pass_rate")  # judge_pass_rate
    r_judge_rate = rm.get("evaluator_pass_rate")
    l_valid_rate = lm.get("valid_verdict_rate")
    r_valid_rate = rm.get("valid_verdict_rate")
    
    # Judge pass rate delta
    judge_rate_delta: float | None = None
    if l_judge_rate is not None and r_judge_rate is not None:
        judge_rate_delta = round(r_judge_rate - l_judge_rate, 4)
    
    # Valid verdict rate delta
    valid_rate_delta: float | None = None
    if l_valid_rate is not None and r_valid_rate is not None:
        valid_rate_delta = round(r_valid_rate - l_valid_rate, 4)

    return {
        "em_delta":         em_delta,
        "l_em":             l_em,
        "r_em":             r_em,
        "l_passed":         l_pas,
        "r_passed":         r_pas,
        "passed_changed":   l_pas != r_pas,
        "status_changed":   left.get("status") != right.get("status"),
        "model_same":       left.get("model") == right.get("model"),
        "verdict":          verdict,           # regression | improvement | no_change
        # Sprint 3B: Taxonomy comparison
        "l_top_failure":    l_top_fail,
        "r_top_failure":    r_top_fail,
        "top_failure_same": l_top_fail == r_top_fail if (l_top_fail and r_top_fail) else None,
        "l_judge_rate":     l_judge_rate,
        "r_judge_rate":     r_judge_rate,
        "judge_rate_delta": judge_rate_delta,
        "l_valid_rate":     l_valid_rate,
        "r_valid_rate":     r_valid_rate,
        "valid_rate_delta": valid_rate_delta,
    }


@app.get("/dashboard/compare", response_class=HTMLResponse, tags=["dashboard"])
def dashboard_compare(
    request: Request,
    left:    Optional[str] = Query(default=None, description="Left (baseline) task_id"),
    right:   Optional[str] = Query(default=None, description="Right (candidate) task_id"),
):
    """
    Side-by-side comparison of two eval runs.
    Shows delta in exact_match_rate + regression / improvement badge.
    """
    nightly = _last_nightly_summary()
    errors:  list[str] = []

    left_run  = None
    right_run = None
    cmp:      dict | None = None

    if left and right:
        left_run  = _fetch_run_for_compare(left)
        right_run = _fetch_run_for_compare(right)
        if left_run is None:
            errors.append(f"Run '{left[:8]}…' not found.")
        if right_run is None:
            errors.append(f"Run '{right[:8]}…' not found.")
        if left_run and right_run:
            cmp = _compare_runs(left_run, right_run)
    elif left or right:
        errors.append("Provide both left= and right= task IDs to compare.")

    # Recent runs for the picker dropdowns (last 50)
    recent_runs = []
    try:
        recent_runs = _exec_query(
            """
            SELECT task_id, model, status, metrics, completed_at
            FROM   eval_runs
            ORDER  BY COALESCE(completed_at, created_at) DESC
            LIMIT  50
            """,
            [],
        )
        recent_runs = [_coerce_run_row(r) for r in recent_runs]
    except Exception:
        pass

    return templates.TemplateResponse(
        "compare.html",
        {
            "request":     request,
            "left_id":     left  or "",
            "right_id":    right or "",
            "left_run":    left_run,
            "right_run":   right_run,
            "cmp":         cmp,
            "errors":      errors,
            "recent_runs": recent_runs,
            "nightly":     nightly,
        },
    )


# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
