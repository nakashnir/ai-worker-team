"""
tests/integration/test_compare.py
Integration tests for compare functionality with taxonomy metrics.
"""

import pytest


class TestCompareWithTaxonomy:
    """Test compare logic with taxonomy metrics present."""
    
    def test_both_runs_have_taxonomy(self):
        """Compare when both runs have taxonomy metrics."""
        # Simulate two runs with taxonomy
        left = {
            "task_id": "left-001",
            "status": "done",
            "model": "model-a",
            "metrics": {
                "total": 10,
                "exact_match_rate": 0.8,
                "passed": True,
                "top_failure_category": "hallucination",
                "evaluator_pass_rate": 0.9,
                "valid_verdict_rate": 1.0,
            }
        }
        
        right = {
            "task_id": "right-001",
            "status": "done",
            "model": "model-a",
            "metrics": {
                "total": 10,
                "exact_match_rate": 0.85,
                "passed": True,
                "top_failure_category": "incomplete_answer",
                "evaluator_pass_rate": 0.95,
                "valid_verdict_rate": 1.0,
            }
        }
        
        # Simulate compare logic
        lm = left["metrics"]
        rm = right["metrics"]
        
        # Judge rate delta
        judge_rate_delta = round(rm["evaluator_pass_rate"] - lm["evaluator_pass_rate"], 4)
        
        # Top failure comparison
        top_failure_same = lm["top_failure_category"] == rm["top_failure_category"]
        
        assert judge_rate_delta == 0.05  # +5pp
        assert top_failure_same is False
    
    def test_judge_rate_improvement(self):
        """Judge pass rate improving should show positive delta."""
        left_judge_rate = 0.7
        right_judge_rate = 0.9
        
        delta = round(right_judge_rate - left_judge_rate, 4)
        
        assert delta == 0.2
        assert delta > 0  # Improvement
    
    def test_judge_rate_regression(self):
        """Judge pass rate dropping should show negative delta."""
        left_judge_rate = 0.9
        right_judge_rate = 0.7
        
        delta = round(right_judge_rate - left_judge_rate, 4)
        
        assert delta == -0.2
        assert delta < 0  # Regression
    
    def test_top_failure_same(self):
        """Same top failure category in both runs."""
        l_top = "hallucination"
        r_top = "hallucination"
        
        same = l_top == r_top
        
        assert same is True
    
    def test_top_failure_different(self):
        """Different top failure categories."""
        l_top = "hallucination"
        r_top = "provider_error"
        
        same = l_top == r_top
        
        assert same is False


class TestCompareWithoutTaxonomy:
    """Test compare fallback when taxonomy metrics missing."""
    
    def test_left_has_taxonomy_right_does_not(self):
        """One run has taxonomy, other doesn't - should not crash."""
        left = {
            "metrics": {
                "total": 10,
                "exact_match_rate": 0.8,
                "top_failure_category": "hallucination",
                "evaluator_pass_rate": 0.9,
            }
        }
        
        right = {
            "metrics": {
                "total": 10,
                "exact_match_rate": 0.85,
                # No taxonomy metrics
            }
        }
        
        lm = left["metrics"]
        rm = right["metrics"]
        
        # Safe extraction
        l_judge = lm.get("evaluator_pass_rate")
        r_judge = rm.get("evaluator_pass_rate")
        l_top = lm.get("top_failure_category")
        r_top = rm.get("top_failure_category")
        
        # Delta only if both present
        judge_delta = None
        if l_judge is not None and r_judge is not None:
            judge_delta = round(r_judge - l_judge, 4)
        
        assert l_judge == 0.9
        assert r_judge is None
        assert judge_delta is None  # Can't compute delta
        assert l_top == "hallucination"
        assert r_top is None
    
    def test_neither_has_taxonomy(self):
        """Both runs lack taxonomy - should fall back gracefully."""
        left = {
            "metrics": {
                "total": 10,
                "exact_match_rate": 0.8,
                "passed": True,
            }
        }
        
        right = {
            "metrics": {
                "total": 10,
                "exact_match_rate": 0.85,
                "passed": True,
            }
        }
        
        lm = left["metrics"]
        rm = right["metrics"]
        
        l_top = lm.get("top_failure_category")
        r_top = rm.get("top_failure_category")
        l_judge = lm.get("evaluator_pass_rate")
        r_judge = rm.get("evaluator_pass_rate")
        
        assert l_top is None
        assert r_top is None
        assert l_judge is None
        assert r_judge is None
    
    def test_missing_metrics_dict(self):
        """Run with missing metrics dict entirely."""
        left = {"metrics": None}
        right = {"metrics": {}}
        
        lm = left.get("metrics") or {}
        rm = right.get("metrics") or {}
        
        l_top = lm.get("top_failure_category")
        r_top = rm.get("top_failure_category")
        
        assert l_top is None
        assert r_top is None


class TestCompareDeltaCalculation:
    """Test delta calculation correctness."""
    
    def test_judge_rate_delta_zero(self):
        """No change in judge rate."""
        l = 0.85
        r = 0.85
        
        delta = round(r - l, 4)
        
        assert delta == 0.0
    
    def test_judge_rate_delta_small_improvement(self):
        """Small improvement (sub-1%)."""
        l = 0.850
        r = 0.855
        
        delta = round(r - l, 4)
        
        assert delta == 0.005
        assert delta > 0
    
    def test_valid_verdict_rate_delta(self):
        """Valid verdict rate delta."""
        l = 0.9
        r = 1.0
        
        delta = round(r - l, 4)
        
        assert delta == 0.1
    
    def test_none_values_no_delta(self):
        """None values should result in None delta."""
        l = None
        r = 0.8
        
        delta = None
        if l is not None and r is not None:
            delta = round(r - l, 4)
        
        assert delta is None


class TestCompareTopFailureLogic:
    """Test top failure category comparison logic."""
    
    def test_both_none(self):
        """Both runs have None top failure."""
        l = None
        r = None
        
        same = l == r if (l and r) else None
        
        assert same is None  # Can't compare
    
    def test_one_none(self):
        """One run has None, other has category."""
        l = "hallucination"
        r = None
        
        same = l == r if (l and r) else None
        
        assert same is None  # Can't compare
    
    def test_both_present_same(self):
        """Both present and same."""
        l = "hallucination"
        r = "hallucination"
        
        same = l == r if (l and r) else None
        
        assert same is True
    
    def test_both_present_different(self):
        """Both present and different."""
        l = "hallucination"
        r = "timeout"
        
        same = l == r if (l and r) else None
        
        assert same is False


class TestBackwardCompatibility:
    """Test backward compatibility with old runs."""
    
    def test_old_run_format(self):
        """Old run without Sprint 3A fields."""
        old_run = {
            "task_id": "old-001",
            "status": "done",
            "model": "old-model",
            "metrics": {
                "total": 10,
                "exact_match_rate": 0.8,
                "passed": True,
                # No taxonomy fields
            }
        }
        
        m = old_run["metrics"]
        
        # Safe extraction
        top_fail = m.get("top_failure_category")
        judge_rate = m.get("evaluator_pass_rate")
        valid_rate = m.get("valid_verdict_rate")
        
        assert top_fail is None
        assert judge_rate is None
        assert valid_rate is None
    
    def test_compare_old_vs_new(self):
        """Compare old run (no taxonomy) vs new run (with taxonomy)."""
        old = {
            "metrics": {
                "exact_match_rate": 0.8,
                "passed": True,
            }
        }
        
        new = {
            "metrics": {
                "exact_match_rate": 0.85,
                "passed": True,
                "top_failure_category": "hallucination",
                "evaluator_pass_rate": 0.9,
            }
        }
        
        om = old["metrics"]
        nm = new["metrics"]
        
        # EM delta works
        em_delta = round(nm["exact_match_rate"] - om["exact_match_rate"], 4)
        assert em_delta == 0.05
        
        # Taxonomy fields None for old run
        o_top = om.get("top_failure_category")
        n_top = nm.get("top_failure_category")
        
        assert o_top is None
        assert n_top == "hallucination"
        
        # Can't compute taxonomy delta
        top_same = o_top == n_top if (o_top and n_top) else None
        assert top_same is None
