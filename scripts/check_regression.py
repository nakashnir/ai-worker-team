#!/usr/bin/env python3
"""
Compare nightly eval metrics against a baseline contract.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"ERROR: file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid JSON in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--baseline",
        default="baselines/eval_valid_v1_baseline.json",
        help="Path to baseline JSON",
    )
    parser.add_argument(
        "--actual",
        required=True,
        help="Path to actual eval-run JSON (from GET /eval/run/{task_id})",
    )
    args = parser.parse_args()

    baseline = _load_json(Path(args.baseline))
    actual = _load_json(Path(args.actual))

    thresholds = baseline.get("thresholds", {})
    min_em = float(thresholds.get("min_exact_match_rate", 1.0))
    require_passed = bool(thresholds.get("require_passed", True))

    metrics = actual.get("metrics", {})
    if not isinstance(metrics, dict):
        print("FAIL: actual payload does not include a metrics object")
        return 1

    status = actual.get("status")
    exact_match_rate = metrics.get("exact_match_rate")
    passed = metrics.get("passed")

    failures: list[str] = []

    expected_dataset = baseline.get("dataset_path")
    if expected_dataset and actual.get("dataset_path") != expected_dataset:
        failures.append(
            "dataset_path mismatch: "
            f"actual={actual.get('dataset_path')!r} expected={expected_dataset!r}"
        )

    expected_scorers = baseline.get("scorers")
    if expected_scorers and actual.get("scorers") != expected_scorers:
        failures.append(
            "scorers mismatch: "
            f"actual={actual.get('scorers')!r} expected={expected_scorers!r}"
        )

    if status != "done":
        failures.append(f"status is {status!r}, expected 'done'")

    try:
        em_value = float(exact_match_rate)
    except (TypeError, ValueError):
        failures.append(f"exact_match_rate is not numeric: {exact_match_rate!r}")
        em_value = -1.0

    if em_value < min_em:
        failures.append(
            f"exact_match_rate {em_value:.4f} is below baseline minimum {min_em:.4f}"
        )

    if require_passed and passed is not True:
        failures.append(f"passed is {passed!r}, expected True")

    print("Regression check summary")
    print(f"- status: {status}")
    print(f"- exact_match_rate: {exact_match_rate}")
    print(f"- passed: {passed}")
    print(f"- min_exact_match_rate: {min_em}")

    if failures:
        print("\nFAIL")
        for line in failures:
            print(f"- {line}")
        return 1

    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
