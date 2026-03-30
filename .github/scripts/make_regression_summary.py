#!/usr/bin/env python3
"""
.github/scripts/make_regression_summary.py  (A12.3)

Scans shared/runs/ for the most recently modified run.json (written by the
nightly local script) and writes:
  artifacts/nightly/<RUN_DATE>/regression-summary.json

in the schema expected by nightly_alert.py.

Env vars consumed (all optional):
  RUN_DATE   Used as the artifact sub-directory (defaults to today UTC).
  DATASET    Dataset path hint written into the summary.

Exits 0 always — a missing or unreadable run.json produces a minimal summary.
"""
from __future__ import annotations
import datetime, json, os, sys
from pathlib import Path


def _find_latest_run_json(runs_dir: str = "shared/runs") -> "str | None":
    candidates = sorted(
        Path(runs_dir).rglob("run.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return str(candidates[0]) if candidates else None


def main() -> None:
    run_date = os.environ.get("RUN_DATE", datetime.datetime.utcnow().strftime("%Y-%m-%d"))
    dataset  = os.environ.get("DATASET",  "")

    dest     = f"artifacts/nightly/{run_date}"
    out_path = f"{dest}/regression-summary.json"

    task_id = model = status = ""
    em_rate = passed = elapsed = None
    ts = datetime.datetime.utcnow().isoformat() + "Z"

    run_json_path = _find_latest_run_json()
    if run_json_path:
        try:
            d = json.load(open(run_json_path))
            s = d.get("summary") or {}
            m = s.get("metrics") or {}
            task_id = d.get("task_id") or ""
            model   = s.get("requested_model") or s.get("effective_model") or ""
            status  = d.get("status") or "done"
            em_rate = m.get("exact_match_rate")
            passed  = m.get("passed")
            elapsed = m.get("elapsed_ms_total")
            ts      = s.get("completed_at") or ts
            if not dataset:
                dataset = s.get("dataset_path") or ""
        except Exception as exc:
            print(f"[regression-summary] warning: could not read {run_json_path}: {exc}",
                  file=sys.stderr)
            status = "unknown"
    else:
        print("[regression-summary] no run.json found — minimal summary", file=sys.stderr)
        status = "unknown"

    summary: dict = {
        "task_id":      task_id,
        "status":       status,
        "model":        model,
        "dataset_path": dataset,
        "pass_fail":    "pass" if passed else "fail",
        "timestamp":    ts,
    }
    if em_rate is not None:
        summary["exact_match_rate"] = em_rate
    if elapsed is not None:
        summary["elapsed_ms_total"] = elapsed

    os.makedirs(dest, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[regression-summary] written: {out_path}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
