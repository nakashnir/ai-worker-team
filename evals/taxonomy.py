"""
evals/taxonomy.py
Failure taxonomy normalization and canonical category definitions.

Provides a single source of truth for failure categories across the system.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────
# Canonical Failure Taxonomy
# ─────────────────────────────────────────────────────────────────

CANONICAL_FAILURE_CATEGORIES = frozenset({
    "hallucination",           # Model invented facts or information
    "incomplete_answer",       # Response missing critical information
    "format_error",            # Response format incorrect or unusable
    "refusal_mismatch",        # Model refused when shouldn't (or vice versa)
    "low_quality_reasoning",   # Reasoning is flawed or unclear
    "judge_parsing_error",     # Judge response couldn't be parsed
    "provider_error",          # Provider/API failure
    "timeout",                 # Request timed out
    "unknown",                 # Unclear why response failed / default fallback
})


# ─────────────────────────────────────────────────────────────────
# Normalization
# ─────────────────────────────────────────────────────────────────

def normalize_failure_category(category: str | None) -> str:
    """
    Normalize a failure category to canonical taxonomy.
    
    Args:
        category: Raw failure category from evaluator
        
    Returns:
        Normalized category from CANONICAL_FAILURE_CATEGORIES or "unknown"
        
    Examples:
        >>> normalize_failure_category("hallucination")
        'hallucination'
        >>> normalize_failure_category("HALLUCINATION")
        'hallucination'
        >>> normalize_failure_category("invalid_category")
        'unknown'
        >>> normalize_failure_category(None)
        'unknown'
        >>> normalize_failure_category("")
        'unknown'
    """
    # Handle None, empty string
    if not category:
        return "unknown"
    
    # Normalize to lowercase and strip whitespace
    normalized = category.strip().lower()
    
    # Check if it's in canonical set
    if normalized in CANONICAL_FAILURE_CATEGORIES:
        return normalized
    
    # Common misspellings / variations
    # (Could expand this mapping over time)
    variations = {
        "hallucinations": "hallucination",
        "incomplete": "incomplete_answer",
        "format": "format_error",
        "refusal": "refusal_mismatch",
        "parsing_error": "judge_parsing_error",
        "provider": "provider_error",
        "api_error": "provider_error",
    }
    
    if normalized in variations:
        return variations[normalized]
    
    # Fallback to unknown for unrecognized categories
    return "unknown"


def get_all_categories() -> frozenset[str]:
    """
    Get the complete set of canonical failure categories.
    
    Returns:
        Immutable set of valid category names
    """
    return CANONICAL_FAILURE_CATEGORIES
