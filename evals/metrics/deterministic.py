"""
evals/metrics/deterministic.py
Deterministic evaluation metrics extracted from workers/app.py.

These are fast, rule-based checks that complement LLM judge evaluation.
"""

from __future__ import annotations

from ..base import Evaluator
from ..schemas import EvalInput, EvalResult, RubricScore


def exact_match(output: str, expected: str | None) -> int:
    """
    Binary exact match check.
    
    Returns:
        1 if output matches expected exactly, 0 otherwise
    """
    if expected is None:
        return 0
    return 1 if output.strip() == expected.strip() else 0


def contains_expected(output: str, expected: str | None) -> int:
    """
    Binary substring containment check.
    
    Returns:
        1 if output contains expected substring, 0 otherwise
    """
    if expected is None:
        return 0
    return 1 if expected.strip() in output.strip() else 0


def nonempty(output: str, expected: str | None = None) -> int:
    """
    Binary non-empty check.
    
    Returns:
        1 if output is non-empty, 0 otherwise
    """
    return 1 if output.strip() else 0


# ─────────────────────────────────────────────────────────────────
# Evaluator wrapper for deterministic metrics
# ─────────────────────────────────────────────────────────────────

class DeterministicEvaluator(Evaluator):
    """
    Evaluator that runs deterministic metrics (exact_match, contains_expected, nonempty).
    Preserves backward compatibility with existing eval.run behavior.
    """
    
    def __init__(self, scorers: list[str] | None = None) -> None:
        """
        Args:
            scorers: List of scorer names to run. 
                     Defaults to ["exact_match", "contains_expected", "format_nonempty"]
        """
        self.scorers = scorers or ["exact_match", "contains_expected", "format_nonempty"]
        
    def evaluate(self, eval_input: EvalInput) -> EvalResult:
        """
        Run deterministic metrics and return structured result.
        """
        output = eval_input.model_output
        expected = eval_input.expected_answer
        
        # Run each scorer
        scores: dict[str, int] = {}
        rubric_scores: list[RubricScore] = []
        
        for scorer in self.scorers:
            if scorer == "exact_match":
                score_val = exact_match(output, expected)
                scores[scorer] = score_val
                rubric_scores.append(RubricScore(
                    key="exact_match",
                    score=float(score_val),
                    passed=bool(score_val),
                    reason="Output exactly matches expected" if score_val else "No exact match",
                    weight=1.0,
                ))
            elif scorer == "contains_expected":
                score_val = contains_expected(output, expected)
                scores[scorer] = score_val
                rubric_scores.append(RubricScore(
                    key="contains_expected",
                    score=float(score_val),
                    passed=bool(score_val),
                    reason="Output contains expected" if score_val else "Expected not found in output",
                    weight=1.0,
                ))
            elif scorer == "format_nonempty":
                score_val = nonempty(output, expected)
                scores[scorer] = score_val
                rubric_scores.append(RubricScore(
                    key="nonempty",
                    score=float(score_val),
                    passed=bool(score_val),
                    reason="Output is non-empty" if score_val else "Output is empty",
                    weight=1.0,
                ))
        
        # Overall passed = exact_match if available
        passed = bool(scores.get("exact_match", 0)) if "exact_match" in self.scorers else None
        
        # Compute overall score as average of all scores
        overall_score = sum(scores.values()) / len(scores) if scores else 0.0
        
        return EvalResult(
            evaluator_name="deterministic",
            score=overall_score,
            passed=passed,
            confidence=1.0,  # Deterministic metrics are always confident
            failure_category=None,
            summary_reason=f"Deterministic metrics: {scores}",
            rubric_scores=rubric_scores,
            metrics=scores,
            raw_judge_output=None,
            error=None,
        )
