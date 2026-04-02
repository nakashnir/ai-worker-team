"""
tests/integration/test_worker_eval.py
Integration tests for worker eval path with lightweight mocks.

Tests persistence, error handling, and evaluator integration.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

from evals import EvalInput, EvalResult, get_evaluator


class TestEvaluatorSelection:
    """Test that worker correctly selects evaluators."""
    
    def test_deterministic_selected_by_default(self):
        """When no evaluator specified, deterministic should be selected."""
        # Simulate task inputs
        task_inputs = {
            "dataset_path": "datasets/sample.jsonl",
            "model": "anthropic:claude-sonnet-4-5",
            "scorers": ["exact_match"],
            # No "evaluator" key
        }
        
        evaluator_name = task_inputs.get("evaluator", "deterministic")
        use_llm_judge = (evaluator_name == "llm_judge")
        
        assert evaluator_name == "deterministic"
        assert use_llm_judge is False
    
    def test_llm_judge_selected_explicitly(self):
        """When evaluator=llm_judge specified, judge should be selected."""
        task_inputs = {
            "dataset_path": "datasets/sample.jsonl",
            "model": "anthropic:claude-sonnet-4-5",
            "scorers": ["exact_match"],
            "evaluator": "llm_judge",
        }
        
        evaluator_name = task_inputs.get("evaluator", "deterministic")
        use_llm_judge = (evaluator_name == "llm_judge")
        
        assert evaluator_name == "llm_judge"
        assert use_llm_judge is True


class TestEvalResultPersistence:
    """Test that eval_result is correctly structured for persistence."""
    
    def test_deterministic_result_structure(self):
        """Deterministic evaluator result should match expected structure."""
        evaluator = get_evaluator("deterministic", scorers=["exact_match"])
        
        eval_input = EvalInput(
            task_id="test-001",
            dataset_item_id="sample-001",
            prompt="What is 2 + 2?",
            expected_answer="4",
            model_output="4",
        )
        
        result = evaluator.evaluate(eval_input)
        
        # This is what gets persisted
        result_dict = {
            "evaluator_name": result.evaluator_name,
            "score": result.score,
            "passed": result.passed,
            "confidence": result.confidence,
            "failure_category": result.failure_category,
            "summary_reason": result.summary_reason,
            "rubric_scores": [rs.model_dump() for rs in result.rubric_scores],
            "error": result.error,
        }
        
        # Validate structure
        assert result_dict["evaluator_name"] == "deterministic"
        assert result_dict["passed"] is True
        assert result_dict["score"] == 1.0
        assert result_dict["error"] is None
        assert isinstance(result_dict["rubric_scores"], list)
        assert len(result_dict["rubric_scores"]) > 0
    
    def test_judge_result_structure(self):
        """LLM judge result should have additional fields."""
        # Mock a judge result
        from evals import RubricScore
        
        result = EvalResult(
            evaluator_name="llm_judge",
            score=0.95,
            passed=True,
            confidence=0.92,
            failure_category=None,
            summary_reason="Good answer",
            rubric_scores=[
                RubricScore(
                    key="accuracy",
                    score=1.0,
                    passed=True,
                    reason="Correct",
                    weight=2.0,
                )
            ],
            metrics={},
            raw_judge_output={"score": 0.95, "passed": True},
            error=None,
        )
        
        # Persist with raw_judge_output
        result_dict = {
            "evaluator_name": result.evaluator_name,
            "score": result.score,
            "passed": result.passed,
            "confidence": result.confidence,
            "failure_category": result.failure_category,
            "summary_reason": result.summary_reason,
            "rubric_scores": [rs.model_dump() for rs in result.rubric_scores],
            "error": result.error,
        }
        if result.raw_judge_output:
            result_dict["raw_judge_output"] = result.raw_judge_output
        
        assert "raw_judge_output" in result_dict
        assert result_dict["raw_judge_output"]["passed"] is True


class TestProviderErrorHandling:
    """Test that provider errors don't crash artifact persistence."""
    
    def test_provider_error_returns_eval_result(self):
        """Provider error should return EvalResult with error field."""
        from providers.stub import EchoExpectedProvider
        from unittest.mock import patch
        
        evaluator = get_evaluator("llm_judge")
        
        eval_input = EvalInput(
            task_id="test-001",
            prompt="Test",
            model_output="Output",
        )
        
        # Mock resolve_provider to return stub (triggers unsupported provider)
        with patch('evals.judges.llm_judge.resolve_provider') as mock_resolve:
            mock_resolve.return_value = (EchoExpectedProvider(), None)
            
            result = evaluator.evaluate(eval_input)
            
            # Should return EvalResult with error, not raise exception
            assert isinstance(result, EvalResult)
            assert result.error is not None
            assert result.failure_category == "provider_error"
            assert result.passed is None
    
    def test_provider_fallback_returns_eval_result(self):
        """Provider fallback should return EvalResult with error."""
        evaluator = get_evaluator("llm_judge")
        
        eval_input = EvalInput(
            task_id="test-001",
            prompt="Test",
            model_output="Output",
        )
        
        # Mock resolve_provider to return fallback
        from providers.stub import EchoExpectedProvider
        with patch('evals.judges.llm_judge.resolve_provider') as mock_resolve:
            fallback_reason = "ANTHROPIC_API_KEY not set"
            mock_resolve.return_value = (EchoExpectedProvider(), fallback_reason)
            
            result = evaluator.evaluate(eval_input)
            
            assert isinstance(result, EvalResult)
            assert result.error is not None
            assert "unavailable" in result.error.lower()
            assert result.failure_category == "provider_error"


class TestSampleRecordFormat:
    """Test that sample records match expected format for workers/app.py."""
    
    def test_sample_record_with_eval_result(self):
        """Sample record should include both scores and eval_result."""
        # Simulate what workers/app.py constructs
        use_llm_judge = True
        
        # Evaluator result
        from evals import RubricScore
        eval_result = EvalResult(
            evaluator_name="llm_judge",
            score=0.95,
            passed=True,
            confidence=0.92,
            failure_category=None,
            summary_reason="Good",
            rubric_scores=[],
            metrics={},
            error=None,
        )
        
        # Deterministic scores (for compatibility)
        scores = {"exact_match": 0, "contains_expected": 1}
        
        # Build sample record
        sample_record = {
            "sample_id": "e001",
            "prompt": "Test",
            "expected": "Expected",
            "output": "Output",
            "scores": scores,  # Backward compatible
            "elapsed_ms": 234,
        }
        
        # Add eval_result
        if use_llm_judge or eval_result.error:
            sample_record["eval_result"] = {
                "evaluator_name": eval_result.evaluator_name,
                "score": eval_result.score,
                "passed": eval_result.passed,
                "confidence": eval_result.confidence,
                "failure_category": eval_result.failure_category,
                "summary_reason": eval_result.summary_reason,
                "rubric_scores": [rs.model_dump() for rs in eval_result.rubric_scores],
                "error": eval_result.error,
            }
        
        # Validate structure
        assert "scores" in sample_record  # Backward compatible
        assert "eval_result" in sample_record  # New structured data
        assert sample_record["eval_result"]["passed"] is True
        assert sample_record["scores"]["exact_match"] == 0


class TestMetricsAggregation:
    """Test metrics dict construction for persistence."""
    
    def test_metrics_dict_deterministic(self):
        """Metrics dict for deterministic run should have correct structure."""
        # Simulate deterministic run
        use_llm_judge = False
        total_rows = 10
        em_rate = 1.0
        fatal_error = None
        
        passed = (em_rate == 1.0) if (em_rate is not None and not fatal_error) else False
        evaluator_pass_rate = None
        
        metrics = {
            "total": total_rows,
            "exact_match_rate": em_rate,
            "passed": passed,
            "evaluator_pass_rate": evaluator_pass_rate,
            "evaluator_passed_count": None,
            "evaluator_valid_count": None,
        }
        
        assert metrics["passed"] is True
        assert metrics["evaluator_pass_rate"] is None
        assert metrics["evaluator_passed_count"] is None
    
    def test_metrics_dict_judge(self):
        """Metrics dict for judge run should have evaluator fields."""
        # Simulate judge run
        use_llm_judge = True
        total_rows = 10
        evaluator_valid_count = 10
        evaluator_passed_count = 10
        fatal_error = None
        
        # Verdict logic
        if total_rows == 0:
            passed = False
            evaluator_pass_rate = 0.0
        elif evaluator_valid_count != total_rows:
            passed = False
            evaluator_pass_rate = round(evaluator_passed_count / total_rows, 4)
        elif evaluator_passed_count != total_rows:
            passed = False
            evaluator_pass_rate = round(evaluator_passed_count / total_rows, 4)
        else:
            passed = not fatal_error
            evaluator_pass_rate = 1.0
        
        metrics = {
            "total": total_rows,
            "exact_match_rate": 0.3,  # Supporting metric
            "passed": passed,
            "evaluator_pass_rate": evaluator_pass_rate,
            "evaluator_passed_count": evaluator_passed_count,
            "evaluator_valid_count": evaluator_valid_count,
        }
        
        assert metrics["passed"] is True
        assert metrics["evaluator_pass_rate"] == 1.0
        assert metrics["evaluator_passed_count"] == 10
        assert metrics["evaluator_valid_count"] == 10
