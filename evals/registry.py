"""
evals/registry.py
Simple evaluator registry/factory.
"""

from __future__ import annotations

from .base import Evaluator
from .judges.llm_judge import LLMJudgeEvaluator
from .metrics.deterministic import DeterministicEvaluator


def get_evaluator(
    evaluator_name: str,
    scorers: list[str] | None = None,
    judge_model: str | None = None,
) -> Evaluator:
    """
    Factory function to get an evaluator by name.
    
    Args:
        evaluator_name: Name of evaluator ("llm_judge" or "deterministic")
        scorers: List of scorer names (for deterministic evaluator)
        judge_model: Model string for LLM judge (defaults to Claude Sonnet)
        
    Returns:
        Evaluator instance
        
    Raises:
        ValueError: If evaluator_name is unknown
    """
    if evaluator_name == "llm_judge":
        model = judge_model or "anthropic:claude-sonnet-4-5-20250929"
        return LLMJudgeEvaluator(judge_model=model)
    
    elif evaluator_name == "deterministic":
        return DeterministicEvaluator(scorers=scorers)
    
    else:
        raise ValueError(
            f"Unknown evaluator: {evaluator_name!r}. "
            f"Known evaluators: llm_judge, deterministic"
        )
