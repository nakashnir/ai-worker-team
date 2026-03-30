#!/usr/bin/env python3
"""
.github/scripts/nightly_alert.py — A12 nightly alert sender (A12.4: workflow-conclusion-wins pass/fail).

Default behavior: posts a generic JSON payload to ALERT_WEBHOOK_URL.
Discord behavior: if ALERT_WEBHOOK_URL contains "discord.com/api/webhooks",
  posts a Discord-compatible {"content": "..."} payload instead.
All other endpoints continue to receive the generic JSON payload unchanged.

Env vars consumed (all optional except ALERT_WEBHOOK_URL):
  ALERT_WEBHOOK_URL   Webhook endpoint. If absent, alert is skipped (non-fatal).
  ALERT_ON_SUCCESS    Set "true" to send on success too. Default: false.
  ALERT_SUMMARY_FILE  Path to regression-summary.json artifact (optional).
  NIGHTLY_STATUS      Workflow conclusion from GitHub Actions context.
  ALERT_TIMESTAMP     ISO-8601 timestamp (defaults to now UTC).
  GITHUB_RUN_URL      URL of the triggering workflow run.
  WORKFLOW_NAME       Name of the triggering workflow.
  GITHUB_REPOSITORY   Repository slug (set automatically by Actions).
  GITHUB_RUN_ID       Run ID (set automatically by Actions).
  TASK_ID             Eval task_id (optional, from summary file or env).
  MODEL               Model identifier (optional, from summary file or env).
  DATASET_PATH        Dataset path (optional, from summary file or env).
  EXACT_MATCH_RATE    Exact-match rate as a float string (optional).
  PASS_FAIL           "pass" or "fail" (optional, derived from status if absent).

Exit codes:
  0  always — alerting failures are logged as warnings, never fatal.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_summary(path: str) -> dict:
    """
    Load regression-summary.json from an artifact path.
    Returns {} on any error — never raises.
    """
    if not path:
        return {}
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as exc:
        print(f"[nightly-alert] warning: could not parse '{path}': {exc}")
        return {}
    return raw if isinstance(raw, dict) else {}


def _first_non_empty(*values):
    """Return the first value that is not None and not a blank string."""
    for v in values:
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        return v
    return None


# ─────────────────────────────────────────────────────────────────
# Discord support (A12.1)
# ─────────────────────────────────────────────────────────────────

def _is_discord_url(url: str) -> bool:
    """Return True if url is a Discord webhook endpoint."""
    return "discord.com/api/webhooks" in url.lower()


def _build_discord_payload(data: dict) -> dict:
    """
    Build a Discord-compatible payload from the generic data dict.
    Discord requires {"content": "<string>"} at minimum.
    Uses plain text — no embeds — to keep it simple and reliable.
    """
    pass_fail   = str(data.get("pass_fail", "unknown")).upper()
    status      = str(data.get("status",    "unknown"))
    icon        = "✅" if pass_fail == "PASS" else "❌"

    lines = [f"{icon} **Nightly Eval — {pass_fail}** (status: `{status}`)"]

    task_id = data.get("task_id")
    if task_id:
        lines.append(f"task: `{task_id}`")

    model = data.get("model")
    if model:
        lines.append(f"model: `{model}`")

    dataset = data.get("dataset_path")
    if dataset:
        lines.append(f"dataset: `{dataset}`")

    em = data.get("exact_match_rate")
    if em is not None:
        try:
            lines.append(f"exact match: `{float(em) * 100:.1f}%`")
        except (TypeError, ValueError):
            lines.append(f"exact match: `{em}`")

    ts = data.get("timestamp")
    if ts:
        lines.append(f"at: `{str(ts)[:19].replace('T', ' ')} UTC`")

    run_url = data.get("github_run_url")
    if run_url:
        lines.append(f"run: {run_url}")

    return {"content": "\n".join(lines)}


# ─────────────────────────────────────────────────────────────────
# Payload construction
# ─────────────────────────────────────────────────────────────────

def _build_payload() -> dict:
    summary = _load_summary(os.getenv("ALERT_SUMMARY_FILE", ""))

    status = _first_non_empty(
        os.getenv("NIGHTLY_STATUS"),
        summary.get("status"),
        "unknown",
    )

    # A12.4: workflow conclusion is the source of truth for top-level pass/fail.
    # The summary artifact may reflect an earlier successful eval step even when
    # the overall workflow conclusion is failure (e.g. a later step failed).
    # Rule: if the workflow conclusion is not success/done, pass_fail is always
    # "fail" — the summary's pass_fail is only trusted on a clean conclusion.
    _status_lower = str(status).strip().lower()
    _workflow_succeeded = _status_lower in {"success", "done"}
    if _workflow_succeeded:
        pass_fail = _first_non_empty(
            os.getenv("PASS_FAIL"),
            summary.get("pass_fail"),
            "pass",
        )
    else:
        pass_fail = "fail"

    payload: dict = {
        "event":             "nightly_regression",
        "status":            status,
        "pass_fail":         pass_fail,
        "task_id":           _first_non_empty(os.getenv("TASK_ID"),          summary.get("task_id")),
        "model":             _first_non_empty(os.getenv("MODEL"),             summary.get("model")),
        "dataset_path":      _first_non_empty(os.getenv("DATASET_PATH"),     summary.get("dataset_path")),
        "exact_match_rate":  _first_non_empty(os.getenv("EXACT_MATCH_RATE"), summary.get("exact_match_rate")),
        "timestamp":         _first_non_empty(
                                 os.getenv("ALERT_TIMESTAMP"),
                                 summary.get("timestamp"),
                                 _now_iso(),
                             ),
        "github_run_url":    _first_non_empty(os.getenv("GITHUB_RUN_URL"),   summary.get("github_run_url")),
        "workflow_name":     _first_non_empty(os.getenv("WORKFLOW_NAME"),    summary.get("workflow_name")),
        "repo":              os.getenv("GITHUB_REPOSITORY"),
        "run_id":            os.getenv("GITHUB_RUN_ID"),
    }

    # Strip None values — keep payload compact and receiver-friendly.
    return {k: v for k, v in payload.items() if v is not None}


# ─────────────────────────────────────────────────────────────────
# Send logic
# ─────────────────────────────────────────────────────────────────

def _should_send(status: str, alert_on_success: bool) -> bool:
    if str(status).strip().lower() == "success" and not alert_on_success:
        return False
    return True


def _post_json(url: str, payload: dict) -> None:
    """
    POST payload as JSON to url.
    Sends explicit User-Agent, Accept, and Content-Type headers.
    Logs warnings on failure; never raises — alerting is non-fatal.
    """
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept":       "application/json",
            "User-Agent":   "EvalOpsNightlyAlerts/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            code = getattr(resp, "status", 200)
            if 200 <= code < 300:
                print(f"[nightly-alert] alert sent (HTTP {code})")
            else:
                print(f"[nightly-alert] warning: webhook returned HTTP {code}")
    except urllib.error.HTTPError as exc:
        print(f"[nightly-alert] warning: webhook HTTP error {exc.code}: {exc.reason}")
    except Exception as exc:
        print(f"[nightly-alert] warning: webhook delivery failed: {exc}")


# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────

def main() -> int:
    webhook_url    = os.getenv("ALERT_WEBHOOK_URL", "").strip()
    alert_on_success = _to_bool(os.getenv("ALERT_ON_SUCCESS"), default=False)

    if not webhook_url:
        print("[nightly-alert] ALERT_WEBHOOK_URL not set — skipping alert (non-fatal).")
        return 0

    payload = _build_payload()
    status  = str(payload.get("status", "unknown"))

    if not _should_send(status, alert_on_success):
        print(f"[nightly-alert] status={status!r} and ALERT_ON_SUCCESS=false — skipping.")
        return 0

    print(f"[nightly-alert] sending alert for status={status!r} ...")
    if _is_discord_url(webhook_url):
        print("[nightly-alert] Discord webhook detected — using Discord payload format.")
        outgoing = _build_discord_payload(payload)
    else:
        outgoing = payload
    _post_json(webhook_url, outgoing)
    # Non-fatal by design: alerting must never block the nightly workflow.
    return 0


if __name__ == "__main__":
    sys.exit(main())
