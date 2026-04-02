# Test Suite Documentation

## Overview

Comprehensive test suite for the ai-worker-team evaluation foundation.

**Stats:**
- 54 tests (all passing)
- <1 second runtime
- 100% schema coverage
- All critical eval paths covered

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements-test.txt

# Run all tests
./run_tests.sh

# Or use pytest directly
pytest tests/ -v
```

---

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Pure logic tests
│   ├── test_schemas.py      # Pydantic validation (11 tests)
│   ├── test_evaluators.py   # Eval logic (22 tests)
│   └── test_verdict_logic.py # Aggregation (12 tests)
└── integration/             # Component integration
    └── test_worker_eval.py  # Persistence & errors (9 tests)
```

---

## Running Tests

### All Tests
```bash
pytest tests/ -v
```

### Specific Category
```bash
pytest tests/unit/ -v                    # Unit tests only
pytest tests/integration/ -v             # Integration tests only
pytest tests/unit/test_schemas.py -v     # Schema tests only
```

### With Coverage
```bash
pytest tests/ --cov=evals --cov-report=term-missing
```

### Single Test
```bash
pytest tests/unit/test_schemas.py::TestEvalInput::test_valid_eval_input -v
```

---

## What's Tested

### ✅ Schema Validation (11 tests)
- EvalInput construction & defaults
- EvalResult with/without errors  
- RubricCriterion & RubricScore
- Missing field validation

### ✅ Deterministic Metrics (9 tests)
- exact_match (success, failure, whitespace)
- contains_expected (substring matching)
- nonempty (empty detection)
- DeterministicEvaluator end-to-end

### ✅ LLM Judge (6 tests)
- Valid JSON parsing
- Malformed JSON handling
- Missing fields graceful degradation
- Markdown fence stripping
- Unsupported provider validation

### ✅ Verdict Logic (12 tests)
- Deterministic: all pass, partial, zero-row, errors
- Judge: all pass, some fail, partial verdicts, zero-row, errors
- Edge cases: single sample, all errors

### ✅ Integration (9 tests)
- Evaluator selection logic
- Persistence format validation
- Provider error handling
- Metrics aggregation correctness

---

## Writing New Tests

### Adding Unit Tests

1. Create test file in `tests/unit/`
2. Import fixtures from `conftest.py`
3. Use pytest class structure:

```python
class TestMyFeature:
    """Test my new feature."""
    
    def test_success_case(self):
        """Feature should work in success case."""
        result = my_feature(input_data)
        assert result.success is True
    
    def test_error_case(self):
        """Feature should handle errors gracefully."""
        result = my_feature(bad_input)
        assert result.error is not None
```

### Using Fixtures

Available fixtures in `conftest.py`:
- `deterministic_evaluator` - DeterministicEvaluator instance
- `eval_input_exact_match` - EvalInput that exact matches
- `eval_input_contains` - EvalInput with substring match
- `eval_input_no_match` - EvalInput with no match
- `mock_judge_pass_response` - Mock judge JSON (pass)
- `mock_judge_fail_response` - Mock judge JSON (fail)

Example:
```python
def test_with_fixture(self, deterministic_evaluator, eval_input_exact_match):
    """Use fixtures instead of manual setup."""
    result = deterministic_evaluator.evaluate(eval_input_exact_match)
    assert result.passed is True
```

---

## Test Patterns

### Testing Evaluators

```python
def test_evaluator():
    evaluator = get_evaluator("deterministic", scorers=["exact_match"])
    eval_input = EvalInput(
        task_id="test",
        prompt="What is 2+2?",
        expected_answer="4",
        model_output="4",
    )
    result = evaluator.evaluate(eval_input)
    assert result.passed is True
```

### Testing Error Paths

```python
def test_error_handling():
    """Errors should return EvalResult, not raise."""
    evaluator = MyEvaluator()
    result = evaluator.evaluate(bad_input)
    
    # Should not raise, should return error in result
    assert result.error is not None
    assert result.failure_category == "expected_category"
```

### Mocking Providers

```python
from unittest.mock import patch

def test_with_mock_provider():
    with patch('evals.judges.llm_judge.resolve_provider') as mock:
        mock.return_value = (MockProvider(), None)
        evaluator = LLMJudgeEvaluator()
        result = evaluator.evaluate(eval_input)
        assert result.passed is True
```

---

## Troubleshooting

### Tests Not Found

```bash
# Ensure pytest.ini is in repo root
cat pytest.ini

# Ensure __init__.py files exist
find tests -name __init__.py
```

### Import Errors

```bash
# Ensure you're running from repo root
cd /path/to/ai-worker-team
pytest tests/ -v

# Check PYTHONPATH
export PYTHONPATH=/path/to/ai-worker-team:$PYTHONPATH
```

### Fixture Not Found

```bash
# Fixtures must be in conftest.py or imported
# Check conftest.py has the fixture definition
grep "def my_fixture" tests/conftest.py
```

---

## CI Integration

### GitHub Actions Example

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements-test.txt
      - run: pytest tests/ -v
```

### Pre-Commit Hook Example

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "Running tests..."
pytest tests/ -v

if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi
```

---

## Coverage Goals

**Current Coverage:**
- Schemas: 100%
- Evaluators: Core paths
- Verdict logic: 100%
- Integration points: Critical paths

**Future Goals:**
- Add coverage reporting to CI
- Maintain >90% coverage on evals/ package
- Add mutation testing for critical paths

---

## FAQ

**Q: Why no end-to-end tests?**  
A: Full e2e requires DB/Redis/filesystem setup. Core logic is tested in isolation, integration points are tested with mocks. E2e smoke tests run in production.

**Q: Why no real API calls?**  
A: Non-deterministic, costs money, requires keys. Parsing and error handling tested thoroughly. Real API tested manually.

**Q: How do I test worker code?**  
A: Worker is monolithic. Extract testable functions or test at integration points (evaluator selection, persistence format).

**Q: Should I add more tests?**  
A: Yes! Add tests for:
- New evaluators
- New schemas
- New verdict logic
- Bug fixes (regression tests)

---

## Maintenance

### Updating Tests

When changing production code:
1. Run tests first to verify current behavior
2. Update tests to match new behavior
3. Ensure tests still pass
4. Add new tests for new functionality

### Deprecating Tests

When removing features:
1. Mark tests as `@pytest.mark.skip("Feature removed")`
2. Delete tests in next sprint
3. Update fixtures if needed

---

## Resources

- [pytest docs](https://docs.pytest.org/)
- [pytest-mock docs](https://pytest-mock.readthedocs.io/)
- [Pydantic testing](https://docs.pydantic.dev/latest/concepts/testing/)

---

## Support

Questions about tests? Check:
1. This README
2. SPRINT2_IMPLEMENTATION_REPORT.md
3. Test code comments
4. conftest.py docstrings
