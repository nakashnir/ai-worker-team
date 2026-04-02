#!/usr/bin/env bash
#
# run_tests.sh
# Test runner for ai-worker-team Sprint 2 test suite
#

set -e

echo "=================================="
echo "AI Worker Team - Test Suite"
echo "=================================="
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest not found. Installing test dependencies..."
    pip install -r requirements-test.txt --break-system-packages
    echo ""
fi

# Run tests with different configurations

echo "📋 Running all tests..."
python -m pytest tests/ -v

echo ""
echo "=================================="
echo "✅ All tests passed!"
echo "=================================="
echo ""

# Optional: Run with coverage
if command -v pytest-cov &> /dev/null; then
    echo "📊 Running with coverage..."
    python -m pytest tests/ --cov=evals --cov-report=term-missing
    echo ""
fi

# Test summary
echo "Test Summary:"
echo "  Unit tests:        ✓"
echo "  Integration tests: ✓"
echo "  Verdict logic:     ✓"
echo "  Schema validation: ✓"
echo ""
