"""
evals/base.py
Abstract evaluator base class.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .schemas import EvalInput, EvalResult


class Evaluator(ABC):
    """
    Abstract base class for all evaluators.
    
    All evaluators must:
    1. Accept EvalInput
    2. Return EvalResult
    3. Handle errors gracefully (return error in EvalResult, don't crash)
    """
    
    @abstractmethod
    def evaluate(self, eval_input: EvalInput) -> EvalResult:
        """
        Evaluate a single model output.
        
        Args:
            eval_input: Packaged evaluation input
            
        Returns:
            EvalResult with structured evaluation outcome
            
        Note:
            Implementations should NOT raise exceptions for evaluation failures.
            Instead, populate EvalResult.error and EvalResult.failure_category.
        """
