"""
tests/conftest.py
Pytest configuration and shared fixtures for ai-worker-team test suite.
"""

import pytest
from pathlib import Path
import sys

# Add repo root to path for imports
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from evals import (
    get_evaluator,
    EvalInput,
    EvalResult,
    RubricCriterion,
    RubricScore,
)
from evals.judges.llm_judge import LLMJudgeEvaluator
from evals.metrics.deterministic import DeterministicEvaluator


# ─────────────────────────────────────────────────────────────────
# Evaluator Fixtures
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def deterministic_evaluator():
    """Deterministic evaluator with all scorers."""
    return get_evaluator(
        "deterministic",
        scorers=["exact_match", "contains_expected", "format_nonempty"]
    )


@pytest.fixture
def deterministic_evaluator_exact_only():
    """Deterministic evaluator with exact_match only."""
    return get_evaluator("deterministic", scorers=["exact_match"])


# ─────────────────────────────────────────────────────────────────
# EvalInput Fixtures
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def eval_input_exact_match():
    """EvalInput that should exact match."""
    return EvalInput(
        task_id="test-001",
        dataset_item_id="sample-001",
        prompt="What is 2 + 2?",
        expected_answer="4",
        model_output="4",
        task_type="eval.run",
        metadata={},
    )


@pytest.fixture
def eval_input_contains():
    """EvalInput where output contains expected but doesn't exact match."""
    return EvalInput(
        task_id="test-002",
        dataset_item_id="sample-002",
        prompt="What is the capital of France?",
        expected_answer="Paris",
        model_output="The capital of France is Paris, a beautiful city.",
        task_type="eval.run",
        metadata={},
    )


@pytest.fixture
def eval_input_no_match():
    """EvalInput where output doesn't match expected."""
    return EvalInput(
        task_id="test-003",
        dataset_item_id="sample-003",
        prompt="What is 2 + 2?",
        expected_answer="4",
        model_output="5",
        task_type="eval.run",
        metadata={},
    )


@pytest.fixture
def eval_input_no_expected():
    """EvalInput with no expected answer (judge-only evaluation)."""
    return EvalInput(
        task_id="test-004",
        dataset_item_id="sample-004",
        prompt="Write a haiku about testing.",
        expected_answer=None,
        model_output="Code runs at last,\nTests reveal what might have been—\nGreen lights bring me peace.",
        task_type="eval.run",
        metadata={},
    )


# ─────────────────────────────────────────────────────────────────
# Mock Provider Fixtures
# ─────────────────────────────────────────────────────────────────

class MockJudgeProvider:
    """Mock provider that returns valid judge JSON."""
    
    def __init__(self, response_json: dict):
        self.response_json = response_json
        self.call_count = 0
    
    def generate(self, prompt: str, max_tokens: int = 2048) -> str:
        """Return mock JSON response."""
        import json
        self.call_count += 1
        return json.dumps(self.response_json)


@pytest.fixture
def mock_judge_pass_response():
    """Mock judge response indicating pass."""
    return {
        "score": 0.95,
        "passed": True,
        "summary_reason": "Answer is correct and well-formatted",
        "failure_category": None,
        "confidence": 0.92,
        "rubric_scores": [
            {
                "key": "answered_user_request",
                "score": 1.0,
                "passed": True,
                "reason": "Directly answered the question",
                "weight": 2.0,
            },
            {
                "key": "factual_accuracy",
                "score": 0.9,
                "passed": True,
                "reason": "Factually correct",
                "weight": 2.0,
            }
        ]
    }


@pytest.fixture
def mock_judge_fail_response():
    """Mock judge response indicating failure."""
    return {
        "score": 0.2,
        "passed": False,
        "summary_reason": "Answer is incorrect",
        "failure_category": "hallucination",
        "confidence": 0.95,
        "rubric_scores": [
            {
                "key": "factual_accuracy",
                "score": 0.0,
                "passed": False,
                "reason": "Factually incorrect",
                "weight": 2.0,
            }
        ]
    }


@pytest.fixture
def mock_judge_malformed_response():
    """Mock judge response that is malformed (not valid JSON)."""
    return "This is not valid JSON, just some text from the model."


@pytest.fixture
def mock_judge_missing_fields_response():
    """Mock judge response missing required fields."""
    return {
        "score": 0.8,
        # Missing: passed, summary_reason, etc.
    }
