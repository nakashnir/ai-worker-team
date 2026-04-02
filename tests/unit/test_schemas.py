"""
tests/unit/test_schemas.py
Unit tests for evals schemas (EvalInput, EvalResult, RubricCriterion, RubricScore).
"""

import pytest
from pydantic import ValidationError

from evals.schemas import (
    EvalInput,
    EvalResult,
    RubricCriterion,
    RubricScore,
)


class TestEvalInput:
    """Test EvalInput schema validation."""
    
    def test_valid_eval_input(self):
        """Valid EvalInput should construct successfully."""
        eval_input = EvalInput(
            task_id="test-001",
            dataset_item_id="sample-001",
            prompt="What is 2 + 2?",
            expected_answer="4",
            model_output="4",
            task_type="eval.run",
            metadata={"category": "math"},
        )
        
        assert eval_input.task_id == "test-001"
        assert eval_input.prompt == "What is 2 + 2?"
        assert eval_input.expected_answer == "4"
        assert eval_input.model_output == "4"
        assert eval_input.metadata["category"] == "math"
    
    def test_eval_input_no_expected(self):
        """EvalInput with None expected_answer should be valid."""
        eval_input = EvalInput(
            task_id="test-002",
            dataset_item_id="sample-002",
            prompt="Write a poem.",
            expected_answer=None,
            model_output="Roses are red...",
            task_type="eval.run",
            metadata={},
        )
        
        assert eval_input.expected_answer is None
    
    def test_eval_input_missing_required(self):
        """EvalInput missing required fields should raise ValidationError."""
        with pytest.raises(ValidationError):
            EvalInput(
                task_id="test-003",
                # Missing: prompt, model_output
                expected_answer="4",
            )
    
    def test_eval_input_default_metadata(self):
        """EvalInput should default metadata to empty dict."""
        eval_input = EvalInput(
            task_id="test-004",
            prompt="Test",
            model_output="Output",
        )
        
        assert eval_input.metadata == {}
        assert eval_input.dataset_item_id is None
        assert eval_input.expected_answer is None


class TestEvalResult:
    """Test EvalResult schema validation."""
    
    def test_valid_eval_result(self):
        """Valid EvalResult should construct successfully."""
        result = EvalResult(
            evaluator_name="llm_judge",
            score=0.95,
            passed=True,
            confidence=0.92,
            failure_category=None,
            summary_reason="Good answer",
            rubric_scores=[],
            metrics={},
            raw_judge_output=None,
            error=None,
        )
        
        assert result.evaluator_name == "llm_judge"
        assert result.score == 0.95
        assert result.passed is True
        assert result.error is None
    
    def test_eval_result_with_error(self):
        """EvalResult with error should be valid."""
        result = EvalResult(
            evaluator_name="llm_judge",
            score=None,
            passed=None,
            confidence=None,
            failure_category="provider_error",
            summary_reason=None,
            rubric_scores=[],
            metrics={},
            raw_judge_output=None,
            error="Provider timeout",
        )
        
        assert result.error == "Provider timeout"
        assert result.failure_category == "provider_error"
        assert result.passed is None
    
    def test_eval_result_defaults(self):
        """EvalResult should use defaults for optional fields."""
        result = EvalResult(
            evaluator_name="deterministic",
        )
        
        assert result.rubric_scores == []
        assert result.metrics == {}
        assert result.score is None
        assert result.passed is None


class TestRubricCriterion:
    """Test RubricCriterion schema validation."""
    
    def test_valid_criterion(self):
        """Valid RubricCriterion should construct successfully."""
        criterion = RubricCriterion(
            key="accuracy",
            label="Factual Accuracy",
            description="Is the response factually correct?",
            weight=2.0,
            required=True,
        )
        
        assert criterion.key == "accuracy"
        assert criterion.weight == 2.0
        assert criterion.required is True
    
    def test_criterion_defaults(self):
        """RubricCriterion should use defaults."""
        criterion = RubricCriterion(
            key="clarity",
            label="Clarity",
            description="Is it clear?",
        )
        
        assert criterion.weight == 1.0
        assert criterion.required is False


class TestRubricScore:
    """Test RubricScore schema validation."""
    
    def test_valid_score(self):
        """Valid RubricScore should construct successfully."""
        score = RubricScore(
            key="accuracy",
            score=0.9,
            passed=True,
            reason="Mostly accurate",
            weight=2.0,
        )
        
        assert score.key == "accuracy"
        assert score.score == 0.9
        assert score.passed is True
    
    def test_score_none_values(self):
        """RubricScore with None values should be valid."""
        score = RubricScore(
            key="clarity",
            score=None,
            passed=None,
            reason=None,
            weight=1.0,
        )
        
        assert score.score is None
        assert score.passed is None
        assert score.reason is None
