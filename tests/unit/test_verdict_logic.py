"""
tests/unit/test_verdict_logic.py
Unit tests for run-level pass/fail verdict aggregation logic.

Tests the logic from workers/app.py lines ~688-710 in isolation.
"""

import pytest


class TestDeterministicVerdictLogic:
    """Test deterministic run-level verdict logic."""
    
    def test_all_samples_exact_match(self):
        """All samples exact match → passed=True."""
        # Simulate deterministic run
        use_llm_judge = False
        total_rows = 10
        exact_match_count = 10
        fatal_error = None
        
        # Logic from workers/app.py
        em_rate = round(exact_match_count / total_rows, 4) if total_rows > 0 else 0.0
        
        if use_llm_judge:
            passed = False
        else:
            passed = (em_rate == 1.0) if (em_rate is not None and not fatal_error) else False
        
        assert em_rate == 1.0
        assert passed is True
    
    def test_partial_exact_match(self):
        """Some samples fail exact match → passed=False."""
        use_llm_judge = False
        total_rows = 10
        exact_match_count = 7
        fatal_error = None
        
        em_rate = round(exact_match_count / total_rows, 4)
        passed = (em_rate == 1.0) if (em_rate is not None and not fatal_error) else False
        
        assert em_rate == 0.7
        assert passed is False
    
    def test_zero_rows_deterministic(self):
        """Zero rows deterministic → passed=False."""
        use_llm_judge = False
        total_rows = 0
        em_rate = None
        fatal_error = None
        
        if use_llm_judge:
            passed = False
        else:
            passed = (em_rate == 1.0) if (em_rate is not None and not fatal_error) else False
        
        assert passed is False
    
    def test_fatal_error_deterministic(self):
        """Fatal error deterministic → passed=False."""
        use_llm_judge = False
        total_rows = 10
        exact_match_count = 10
        fatal_error = "Provider timeout"
        
        em_rate = 1.0
        passed = (em_rate == 1.0) if (em_rate is not None and not fatal_error) else False
        
        assert passed is False


class TestJudgeVerdictLogic:
    """Test LLM judge run-level verdict logic."""
    
    def test_all_samples_pass_judge(self):
        """All samples pass judge → passed=True."""
        use_llm_judge = True
        total_rows = 10
        evaluator_valid_count = 10
        evaluator_passed_count = 10
        fatal_error = None
        
        # Logic from workers/app.py (Sprint 1.1.2)
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
        
        assert passed is True
        assert evaluator_pass_rate == 1.0
    
    def test_some_samples_fail_judge(self):
        """Some samples fail judge → passed=False."""
        use_llm_judge = True
        total_rows = 10
        evaluator_valid_count = 10
        evaluator_passed_count = 7
        fatal_error = None
        
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
        
        assert passed is False
        assert evaluator_pass_rate == 0.7
    
    def test_partial_verdicts_judge(self):
        """Some samples lack valid verdict → passed=False (Sprint 1.1.1 fix)."""
        use_llm_judge = True
        total_rows = 10
        evaluator_valid_count = 8  # 2 samples had errors
        evaluator_passed_count = 8
        fatal_error = None
        
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
        
        assert passed is False
        assert evaluator_pass_rate == 0.8
        # Run fails because not all samples have valid verdicts
    
    def test_zero_rows_judge(self):
        """Zero rows judge → passed=False (Sprint 1.1.2 fix)."""
        use_llm_judge = True
        total_rows = 0
        evaluator_valid_count = 0
        evaluator_passed_count = 0
        fatal_error = None
        
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
        
        assert passed is False
        assert evaluator_pass_rate == 0.0
    
    def test_fatal_error_judge(self):
        """Fatal error with all samples passing → passed=False."""
        use_llm_judge = True
        total_rows = 10
        evaluator_valid_count = 10
        evaluator_passed_count = 10
        fatal_error = "Provider timeout"
        
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
            passed = not fatal_error  # not "Provider timeout" = False
            evaluator_pass_rate = 1.0
        
        assert passed is False
        assert evaluator_pass_rate == 1.0


class TestEdgeCases:
    """Test edge cases in verdict logic."""
    
    def test_single_sample_pass(self):
        """Single sample passing should work correctly."""
        use_llm_judge = True
        total_rows = 1
        evaluator_valid_count = 1
        evaluator_passed_count = 1
        fatal_error = None
        
        if total_rows == 0:
            passed = False
        elif evaluator_valid_count != total_rows:
            passed = False
        elif evaluator_passed_count != total_rows:
            passed = False
        else:
            passed = not fatal_error
        
        assert passed is True
    
    def test_single_sample_fail(self):
        """Single sample failing should work correctly."""
        use_llm_judge = True
        total_rows = 1
        evaluator_valid_count = 1
        evaluator_passed_count = 0
        fatal_error = None
        
        if total_rows == 0:
            passed = False
        elif evaluator_valid_count != total_rows:
            passed = False
        elif evaluator_passed_count != total_rows:
            passed = False
        else:
            passed = not fatal_error
        
        assert passed is False
    
    def test_all_samples_error_no_verdicts(self):
        """All samples errored (no valid verdicts) → passed=False."""
        use_llm_judge = True
        total_rows = 10
        evaluator_valid_count = 0  # All errors
        evaluator_passed_count = 0
        fatal_error = None
        
        if total_rows == 0:
            passed = False
        elif evaluator_valid_count != total_rows:
            passed = False
        elif evaluator_passed_count != total_rows:
            passed = False
        else:
            passed = not fatal_error
        
        assert passed is False
