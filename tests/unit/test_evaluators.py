"""
tests/unit/test_evaluators.py
Unit tests for evaluators (DeterministicEvaluator, LLMJudgeEvaluator).
"""

import pytest
import json
from unittest.mock import Mock, patch

from evals import get_evaluator
from evals.judges.llm_judge import LLMJudgeEvaluator
from evals.metrics.deterministic import (
    DeterministicEvaluator,
    exact_match,
    contains_expected,
    nonempty,
)


class TestDeterministicMetrics:
    """Test individual deterministic metric functions."""
    
    def test_exact_match_success(self):
        """exact_match should return 1 when output matches expected."""
        assert exact_match("4", "4") == 1
        assert exact_match("Paris", "Paris") == 1
    
    def test_exact_match_failure(self):
        """exact_match should return 0 when output doesn't match."""
        assert exact_match("5", "4") == 0
        assert exact_match("Paris", "London") == 0
        assert exact_match("The answer is Paris", "Paris") == 0
    
    def test_exact_match_whitespace(self):
        """exact_match should strip whitespace."""
        assert exact_match("  4  ", "4") == 1
        assert exact_match("4", "  4  ") == 1
    
    def test_exact_match_none_expected(self):
        """exact_match should return 0 when expected is None."""
        assert exact_match("anything", None) == 0
    
    def test_contains_expected_success(self):
        """contains_expected should return 1 when output contains expected."""
        assert contains_expected("The answer is 4", "4") == 1
        assert contains_expected("Paris is the capital", "Paris") == 1
    
    def test_contains_expected_failure(self):
        """contains_expected should return 0 when expected not in output."""
        assert contains_expected("The answer is 5", "4") == 0
        assert contains_expected("London is the capital", "Paris") == 0
    
    def test_contains_expected_none(self):
        """contains_expected should return 0 when expected is None."""
        assert contains_expected("anything", None) == 0
    
    def test_nonempty_success(self):
        """nonempty should return 1 for non-empty output."""
        assert nonempty("4", None) == 1
        assert nonempty("anything", "expected") == 1
        assert nonempty("  text  ", None) == 1
    
    def test_nonempty_failure(self):
        """nonempty should return 0 for empty output."""
        assert nonempty("", None) == 0
        assert nonempty("   ", None) == 0


class TestDeterministicEvaluator:
    """Test DeterministicEvaluator."""
    
    def test_evaluate_all_pass(self, deterministic_evaluator, eval_input_exact_match):
        """All metrics should pass for exact match."""
        result = deterministic_evaluator.evaluate(eval_input_exact_match)
        
        assert result.evaluator_name == "deterministic"
        assert result.passed is True
        assert result.score == 1.0
        assert result.error is None
        assert result.metrics["exact_match"] == 1
        assert result.metrics["contains_expected"] == 1
        assert result.metrics["format_nonempty"] == 1
    
    def test_evaluate_contains_only(self, deterministic_evaluator, eval_input_contains):
        """Only contains_expected and nonempty should pass."""
        result = deterministic_evaluator.evaluate(eval_input_contains)
        
        assert result.passed is False  # exact_match failed
        assert result.metrics["exact_match"] == 0
        assert result.metrics["contains_expected"] == 1
        assert result.metrics["format_nonempty"] == 1
        # Score is average: (0 + 1 + 1) / 3 = 0.666...
        assert 0.66 < result.score < 0.67
    
    def test_evaluate_all_fail(self, deterministic_evaluator, eval_input_no_match):
        """All metrics except nonempty should fail."""
        result = deterministic_evaluator.evaluate(eval_input_no_match)
        
        assert result.passed is False
        assert result.metrics["exact_match"] == 0
        assert result.metrics["contains_expected"] == 0
        assert result.metrics["format_nonempty"] == 1
    
    def test_evaluate_exact_match_only(self, deterministic_evaluator_exact_only, eval_input_exact_match):
        """Evaluator with only exact_match scorer."""
        result = deterministic_evaluator_exact_only.evaluate(eval_input_exact_match)
        
        assert result.passed is True
        assert result.score == 1.0
        assert len(result.metrics) == 1
        assert result.metrics["exact_match"] == 1
    
    def test_rubric_scores_generated(self, deterministic_evaluator, eval_input_exact_match):
        """Deterministic evaluator should generate rubric scores."""
        result = deterministic_evaluator.evaluate(eval_input_exact_match)
        
        assert len(result.rubric_scores) == 3
        keys = {rs.key for rs in result.rubric_scores}
        assert keys == {"exact_match", "contains_expected", "nonempty"}


class TestLLMJudgeEvaluator:
    """Test LLMJudgeEvaluator."""
    
    def test_parse_valid_judge_response(self, mock_judge_pass_response):
        """LLM judge should parse valid JSON response."""
        evaluator = LLMJudgeEvaluator()
        
        # Create eval input directly
        from evals import EvalInput
        eval_input = EvalInput(
            task_id="test-001",
            dataset_item_id="sample-001",
            prompt="What is 2 + 2?",
            expected_answer="4",
            model_output="4",
            task_type="eval.run",
            metadata={},
        )
        
        # Test the parsing method directly
        response_json = json.dumps(mock_judge_pass_response)
        result = evaluator._parse_judge_response(response_json, eval_input)
        
        assert result.evaluator_name == "llm_judge"
        assert result.passed is True
        assert result.score == 0.95
        assert result.confidence == 0.92
        assert result.failure_category is None
        assert result.error is None
        assert len(result.rubric_scores) == 2
    
    def test_parse_malformed_json(self):
        """LLM judge should handle malformed JSON gracefully."""
        evaluator = LLMJudgeEvaluator()
        
        from evals import EvalInput
        eval_input = EvalInput(
            task_id="test",
            prompt="test",
            model_output="test",
        )
        
        malformed = "This is not JSON"
        result = evaluator._parse_judge_response(malformed, eval_input)
        
        assert result.evaluator_name == "llm_judge"
        assert result.passed is None
        assert result.error is not None
        assert "parse" in result.error.lower()
        assert result.failure_category == "judge_parsing_error"
    
    def test_parse_json_missing_fields(self):
        """LLM judge should handle JSON missing required fields."""
        evaluator = LLMJudgeEvaluator()
        
        from evals import EvalInput
        eval_input = EvalInput(
            task_id="test",
            prompt="test",
            model_output="test",
        )
        
        incomplete = json.dumps({"score": 0.8})  # Missing passed, etc.
        result = evaluator._parse_judge_response(incomplete, eval_input)
        
        assert result.evaluator_name == "llm_judge"
        # Should still parse what it can
        assert result.score == 0.8
        assert result.passed is None  # Missing field becomes None
    
    def test_parse_with_markdown_fencing(self, mock_judge_pass_response):
        """LLM judge should strip markdown code fences."""
        evaluator = LLMJudgeEvaluator()
        
        from evals import EvalInput
        eval_input = EvalInput(
            task_id="test",
            prompt="test",
            model_output="test",
        )
        
        # Wrap valid JSON in markdown
        fenced = f"```json\n{json.dumps(mock_judge_pass_response)}\n```"
        result = evaluator._parse_judge_response(fenced, eval_input)
        
        assert result.passed is True
        assert result.score == 0.95
        assert result.error is None
    
    def test_unsupported_provider_error(self):
        """LLM judge should return error for non-Anthropic provider."""
        from evals import EvalInput
        from providers.stub import EchoExpectedProvider
        
        evaluator = LLMJudgeEvaluator()
        eval_input = EvalInput(
            task_id="test",
            prompt="test",
            model_output="test",
        )
        
        # Patch resolve_provider to return stub
        with patch('evals.judges.llm_judge.resolve_provider') as mock_resolve:
            mock_resolve.return_value = (EchoExpectedProvider(), None)
            
            result = evaluator.evaluate(eval_input)
            
            assert result.evaluator_name == "llm_judge"
            assert result.error is not None
            assert "Anthropic provider" in result.error
            assert result.failure_category == "provider_error"


class TestEvaluatorRegistry:
    """Test get_evaluator registry function."""
    
    def test_get_deterministic(self):
        """get_evaluator should return DeterministicEvaluator."""
        evaluator = get_evaluator("deterministic", scorers=["exact_match"])
        assert isinstance(evaluator, DeterministicEvaluator)
    
    def test_get_llm_judge(self):
        """get_evaluator should return LLMJudgeEvaluator."""
        evaluator = get_evaluator("llm_judge")
        assert isinstance(evaluator, LLMJudgeEvaluator)
    
    def test_get_unknown_evaluator(self):
        """get_evaluator should raise ValueError for unknown evaluator."""
        with pytest.raises(ValueError, match="Unknown evaluator"):
            get_evaluator("unknown_evaluator")
