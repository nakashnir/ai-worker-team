"""
evals/schemas.py
Structured evaluation schemas for LLM-as-a-Judge and deterministic metrics.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────
# Rubric schemas
# ─────────────────────────────────────────────────────────────────

class RubricCriterion(BaseModel):
    """
    A single criterion in an evaluation rubric.
    """
    key: str = Field(..., description="Unique identifier for this criterion")
    label: str = Field(..., description="Human-readable label")
    description: str = Field(..., description="What this criterion measures")
    weight: float = Field(1.0, description="Relative weight in scoring")
    required: bool = Field(False, description="Whether this criterion must be satisfied")


class RubricScore(BaseModel):
    """
    Score result for a single rubric criterion.
    """
    key: str = Field(..., description="Criterion key")
    score: float | None = Field(None, description="Numeric score (0-1 typical)")
    passed: bool | None = Field(None, description="Binary pass/fail if applicable")
    reason: str | None = Field(None, description="Brief explanation for this score")
    weight: float = Field(1.0, description="Weight used in aggregation")


# ─────────────────────────────────────────────────────────────────
# Evaluation input/output schemas
# ─────────────────────────────────────────────────────────────────

class EvalInput(BaseModel):
    """
    Input to an evaluator.
    Packages everything needed to judge a single model output.
    """
    task_id: str = Field(..., description="Parent task identifier")
    dataset_item_id: str | None = Field(None, description="Sample ID from dataset")
    prompt: str = Field(..., description="Input prompt given to the model")
    expected_answer: str | None = Field(None, description="Reference answer if available")
    model_output: str = Field(..., description="Actual model response")
    task_type: str | None = Field(None, description="Type of task (e.g., qa, summarization)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    rubric: list[RubricCriterion] | None = Field(None, description="Evaluation criteria")


class EvalResult(BaseModel):
    """
    Structured evaluation result from any evaluator.
    Core contract: all evaluators return this schema.
    """
    evaluator_name: str = Field(..., description="Which evaluator produced this result")
    score: float | None = Field(None, description="Overall score (0-1 typical)")
    passed: bool | None = Field(None, description="Binary pass/fail if applicable")
    confidence: float | None = Field(None, description="Evaluator's confidence (0-1)")
    failure_category: str | None = Field(None, description="Taxonomy category if failed")
    summary_reason: str | None = Field(None, description="Brief explanation of the result")
    rubric_scores: list[RubricScore] = Field(default_factory=list, description="Per-criterion scores")
    metrics: dict[str, Any] = Field(default_factory=dict, description="Additional metrics")
    raw_judge_output: dict[str, Any] | None = Field(None, description="Raw LLM response if applicable")
    error: str | None = Field(None, description="Error message if evaluation failed")
