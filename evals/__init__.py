"""
evals/__init__.py
Evaluation framework for ai-worker-team.

Provides:
- Structured evaluation schemas (EvalInput, EvalResult)
- Evaluator base class and registry
- LLM-as-a-Judge evaluator
- Deterministic metrics evaluator
"""

from .base import Evaluator
from .registry import get_evaluator
from .schemas import (
    EvalInput,
    EvalResult,
    RubricCriterion,
    RubricScore,
)
from .judges import LLMJudgeEvaluator
from .metrics import DeterministicEvaluator

__all__ = [
    "Evaluator",
    "get_evaluator",
    "EvalInput",
    "EvalResult",
    "RubricCriterion",
    "RubricScore",
    "LLMJudgeEvaluator",
    "DeterministicEvaluator",
]
