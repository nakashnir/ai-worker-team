"""
tests/unit/test_taxonomy.py
Unit tests for failure taxonomy normalization.
"""

import pytest

from evals.taxonomy import (
    normalize_failure_category,
    get_all_categories,
    CANONICAL_FAILURE_CATEGORIES,
)


class TestCategoryNormalization:
    """Test normalize_failure_category function."""
    
    def test_valid_categories_passthrough(self):
        """Valid canonical categories should pass through unchanged."""
        for category in CANONICAL_FAILURE_CATEGORIES:
            assert normalize_failure_category(category) == category
    
    def test_uppercase_normalization(self):
        """Uppercase categories should normalize to lowercase."""
        assert normalize_failure_category("HALLUCINATION") == "hallucination"
        assert normalize_failure_category("Provider_Error") == "provider_error"
        assert normalize_failure_category("TIMEOUT") == "timeout"
    
    def test_whitespace_stripping(self):
        """Whitespace should be stripped."""
        assert normalize_failure_category("  hallucination  ") == "hallucination"
        assert normalize_failure_category("\ttimeout\n") == "timeout"
    
    def test_none_fallback(self):
        """None should fallback to 'unknown'."""
        assert normalize_failure_category(None) == "unknown"
    
    def test_empty_string_fallback(self):
        """Empty string should fallback to 'unknown'."""
        assert normalize_failure_category("") == "unknown"
        assert normalize_failure_category("   ") == "unknown"
    
    def test_invalid_category_fallback(self):
        """Invalid categories should fallback to 'unknown'."""
        assert normalize_failure_category("invalid_category") == "unknown"
        assert normalize_failure_category("nonsense") == "unknown"
        assert normalize_failure_category("123456") == "unknown"
    
    def test_common_variations(self):
        """Common variations should map to canonical categories."""
        # Plural -> singular
        assert normalize_failure_category("hallucinations") == "hallucination"
        
        # Short forms
        assert normalize_failure_category("incomplete") == "incomplete_answer"
        assert normalize_failure_category("format") == "format_error"
        assert normalize_failure_category("refusal") == "refusal_mismatch"
        
        # Alternative names
        assert normalize_failure_category("parsing_error") == "judge_parsing_error"
        assert normalize_failure_category("provider") == "provider_error"
        assert normalize_failure_category("api_error") == "provider_error"
    
    def test_mixed_case_variations(self):
        """Variations should work with mixed case."""
        assert normalize_failure_category("HALLUCINATIONS") == "hallucination"
        assert normalize_failure_category("Api_Error") == "provider_error"


class TestCanonicalTaxonomy:
    """Test canonical taxonomy set."""
    
    def test_taxonomy_size(self):
        """Should have exactly 9 canonical categories."""
        assert len(CANONICAL_FAILURE_CATEGORIES) == 9
    
    def test_required_categories_present(self):
        """All required categories should be present."""
        required = {
            "hallucination",
            "incomplete_answer",
            "format_error",
            "refusal_mismatch",
            "low_quality_reasoning",
            "judge_parsing_error",
            "provider_error",
            "timeout",
            "unknown",
        }
        assert CANONICAL_FAILURE_CATEGORIES == required
    
    def test_get_all_categories(self):
        """get_all_categories should return the canonical set."""
        categories = get_all_categories()
        assert categories == CANONICAL_FAILURE_CATEGORIES
        assert isinstance(categories, frozenset)


class TestEdgeCases:
    """Test edge cases in normalization."""
    
    def test_special_characters(self):
        """Categories with special characters should fallback to unknown."""
        assert normalize_failure_category("error!") == "unknown"
        assert normalize_failure_category("test@category") == "unknown"
    
    def test_numeric_strings(self):
        """Numeric strings should fallback to unknown."""
        assert normalize_failure_category("404") == "unknown"
        assert normalize_failure_category("500") == "unknown"
    
    def test_very_long_string(self):
        """Very long invalid strings should fallback to unknown."""
        long_invalid = "a" * 1000
        assert normalize_failure_category(long_invalid) == "unknown"
    
    def test_unicode_characters(self):
        """Unicode characters should be handled."""
        assert normalize_failure_category("hallucination™") == "unknown"
        assert normalize_failure_category("错误") == "unknown"
