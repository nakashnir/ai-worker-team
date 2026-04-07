"""
tests/integration/test_dashboard_product.py
Integration tests for Sprint D: dashboard productization layer.

Tests:
- GET /dashboard/connect returns 200
- GET /dashboard/new returns 200 with form elements
- POST /dashboard/new with valid fields creates a task in Redis
- POST /dashboard/new with missing description returns 422
"""

import json
from unittest.mock import MagicMock, patch, mock_open

import pytest
from starlette.requests import Request

import orchestrator.app as app_module


def _make_request(query_string=b""):
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/dashboard/connect",
        "headers": [],
        "query_string": query_string,
    })


class TestConnectPage:
    """Tests for GET /dashboard/connect."""

    def test_connect_page_returns_200(self, monkeypatch):
        """GET /dashboard/connect should return 200 with dataset info."""
        monkeypatch.setattr(app_module, "SHARED_DIR", app_module.SHARED_DIR)

        def fake_datasets():
            return ["sample.jsonl", "nightly_eval_curated_v1.jsonl"]

        monkeypatch.setattr(app_module, "_available_datasets", fake_datasets)
        monkeypatch.setattr(
            app_module,
            "_last_nightly_summary",
            lambda: {"available": False},
        )
        monkeypatch.setattr(
            app_module,
            "_exec_query",
            lambda *a, **kw: [],
        )

        request = _make_request()
        response = app_module.dashboard_connect(request=request)

        assert response.status_code == 200
        body = response.body.decode("utf-8")
        assert "nightly_eval_curated_v1.jsonl" in body
        assert "How to Connect" in body

    def test_connect_empty_datasets(self, monkeypatch):
        """Should still render when no datasets exist."""
        monkeypatch.setattr(app_module, "_available_datasets", lambda: [])
        monkeypatch.setattr(
            app_module, "_last_nightly_summary", lambda: {"available": False}
        )

        request = _make_request()
        response = app_module.dashboard_connect(request=request)

        assert response.status_code == 200


class TestNewEvalPage:
    """Tests for GET /dashboard/new."""

    def test_new_eval_page_returns_200(self, monkeypatch):
        """GET /dashboard/new should render form with dataset options."""
        monkeypatch.setattr(
            app_module, "_available_datasets", lambda: ["test.jsonl"]
        )
        monkeypatch.setattr(app_module, "_distinct_models", lambda: [])
        monkeypatch.setattr(
            app_module, "_last_nightly_summary", lambda: {"available": False}
        )

        request = _make_request()
        response = app_module.dashboard_new(request=request)

        assert response.status_code == 200
        body = response.body.decode("utf-8")
        assert "Create Evaluation" in body
        assert "test.jsonl" in body
        assert "exact_match" in body


class TestNewEvalFormSubmission:
    """Tests for POST /dashboard/new."""

    def _build_form(self, **fields):
        """Build a dict simulating form data."""
        defaults = {
            "description": "Test eval run",
            "task_type": "eval.run",
            "model": "anthropic:claude-sonnet-4-5-20250929",
            "dataset_path": "datasets/nightly_eval_curated_v1.jsonl",
            "evaluator": "deterministic",
            "judge_model": None,
            "scorers": ["exact_match"],
            "rubric_json": None,
        }
        defaults.update(fields)
        return defaults

    def test_new_eval_form_post_creates_task(self, monkeypatch):
        """Valid form should push a task to Redis."""
        pushed: list = []

        class FakeRedis:
            def lpush(self, queue, payload):
                pushed.append(json.loads(payload))

        monkeypatch.setattr(app_module, "get_redis", lambda: FakeRedis())
        monkeypatch.setattr(
            app_module, "_available_datasets", lambda: ["nightly_eval_curated_v1.jsonl"]
        )

        response = app_module.dashboard_new_submit(
            request=_make_request(),
            description="Test eval run",
            task_type="eval.run",
            model="anthropic:claude-sonnet-4-5-20250929",
            dataset_path="datasets/nightly_eval_curated_v1.jsonl",
            evaluator="deterministic",
            judge_model=None,
            scorers=["exact_match"],
            rubric_json=None,
        )

        assert len(pushed) == 1
        task = pushed[0]
        assert task["task_type"] == "eval.run"
        assert task["description"] == "Test eval run"
        assert task["inputs"]["dataset_path"] == "datasets/nightly_eval_curated_v1.jsonl"
        assert task["inputs"]["scorers"] == ["exact_match"]

        # Redirect to /dashboard
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"

    def test_new_eval_missing_description_returns_422(self, monkeypatch):
        """Empty description should return 422 with error message."""
        monkeypatch.setattr(
            app_module, "_available_datasets", lambda: ["test.jsonl"]
        )
        monkeypatch.setattr(app_module, "_distinct_models", lambda: [])
        monkeypatch.setattr(
            app_module, "_last_nightly_summary", lambda: {"available": False}
        )

        response = app_module.dashboard_new_submit(
            request=_make_request(),
            description="",
            task_type="eval.run",
            model=None,
            dataset_path="datasets/test.jsonl",
            evaluator="deterministic",
            judge_model=None,
            scorers=["exact_match"],
            rubric_json=None,
        )

        assert response.status_code == 422
        body = response.body.decode("utf-8")
        assert "Description is required" in body

    def test_new_eval_missing_dataset_returns_422(self, monkeypatch):
        """Missing dataset_path should return 422."""
        monkeypatch.setattr(
            app_module, "_available_datasets", lambda: []
        )
        monkeypatch.setattr(app_module, "_distinct_models", lambda: [])
        monkeypatch.setattr(
            app_module, "_last_nightly_summary", lambda: {"available": False}
        )

        response = app_module.dashboard_new_submit(
            request=_make_request(),
            description="Some description",
            task_type="eval.run",
            model=None,
            dataset_path=None,
            evaluator="deterministic",
            judge_model=None,
            scorers=["exact_match"],
            rubric_json=None,
        )

        assert response.status_code == 422
        body = response.body.decode("utf-8")
        assert "Dataset path is required" in body

    def test_new_eval_malformed_rubric_returns_422(self, monkeypatch):
        """Invalid JSON in rubric field should return 422."""
        monkeypatch.setattr(
            app_module, "_available_datasets", lambda: ["test.jsonl"]
        )
        monkeypatch.setattr(app_module, "_distinct_models", lambda: [])
        monkeypatch.setattr(
            app_module, "_last_nightly_summary", lambda: {"available": False}
        )

        response = app_module.dashboard_new_submit(
            request=_make_request(),
            description="Test with bad rubric",
            task_type="eval.run",
            dataset_path="datasets/test.jsonl",
            evaluator="llm_judge",
            rubric_json="{not valid json!",
            scorers=["exact_match"],
        )

        assert response.status_code == 422
        body = response.body.decode("utf-8")
        assert "Invalid JSON in custom rubric" in body

    def test_new_eval_with_rubric_pushes_task(self, monkeypatch):
        """Valid rubric JSON should be included in task inputs."""
        pushed: list = []

        class FakeRedis:
            def lpush(self, queue, payload):
                pushed.append(json.loads(payload))

        monkeypatch.setattr(app_module, "get_redis", lambda: FakeRedis())
        monkeypatch.setattr(
            app_module, "_available_datasets", lambda: ["test.jsonl"]
        )

        rubric = [{"key": "quality", "label": "Quality", "description": "Is it good?", "weight": 1.0, "required": True}]

        response = app_module.dashboard_new_submit(
            request=_make_request(),
            description="Test with rubric",
            task_type="eval.run",
            model="anthropic:claude-sonnet-4-5-20250929",
            dataset_path="datasets/test.jsonl",
            evaluator="llm_judge",
            judge_model="anthropic:claude-sonnet-4-5-20250929",
            scorers=["exact_match"],
            rubric_json=json.dumps(rubric),
        )

        assert len(pushed) == 1
        task = pushed[0]
        assert task["inputs"]["evaluator"] == "llm_judge"
        assert task["inputs"]["rubric"] == rubric
        assert task["inputs"]["judge_model"] == "anthropic:claude-sonnet-4-5-20250929"
        assert response.status_code == 303

    def test_new_eval_dataset_not_exists_returns_422(self, monkeypatch):
        """Existing dataset_path but file not in shared area should return 422 and NOT queue."""
        pushed: list = []

        class FakeRedis:
            def lpush(self, queue, payload):
                pushed.append(json.loads(payload))

        monkeypatch.setattr(app_module, "get_redis", lambda: FakeRedis())
        monkeypatch.setattr(
            app_module, "_available_datasets", lambda: ["other.jsonl"]
        )
        monkeypatch.setattr(app_module, "_distinct_models", lambda: [])
        monkeypatch.setattr(
            app_module, "_last_nightly_summary", lambda: {"available": False}
        )

        response = app_module.dashboard_new_submit(
            request=_make_request(),
            description="Test missing dataset",
            task_type="eval.run",
            model="anthropic:claude-sonnet-4-5-20250929",
            dataset_path="datasets/test.jsonl",
            evaluator="deterministic",
            judge_model=None,
            scorers=["exact_match"],
            rubric_json=None,
        )

        assert response.status_code == 422
        body = response.body.decode("utf-8")
        assert "does not exist in the shared datasets area" in body
        assert len(pushed) == 0

    def test_new_eval_dataset_exists_succeeds(self, monkeypatch):
        """Dataset that exists in _available_datasets should queue a task."""
        pushed: list = []

        class FakeRedis:
            def lpush(self, queue, payload):
                pushed.append(json.loads(payload))

        monkeypatch.setattr(app_module, "get_redis", lambda: FakeRedis())
        monkeypatch.setattr(
            app_module, "_available_datasets", lambda: ["test.jsonl"]
        )
        monkeypatch.setattr(app_module, "_distinct_models", lambda: [])
        monkeypatch.setattr(
            app_module, "_last_nightly_summary", lambda: {"available": False}
        )

        response = app_module.dashboard_new_submit(
            request=_make_request(),
            description="Test eval run",
            task_type="eval.run",
            model="anthropic:claude-sonnet-4-5-20250929",
            dataset_path="datasets/test.jsonl",
            evaluator="deterministic",
            judge_model=None,
            scorers=["exact_match"],
            rubric_json=None,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"
        assert len(pushed) == 1
        assert pushed[0]["inputs"]["dataset_path"] == "datasets/test.jsonl"

    def test_new_eval_dataset_path_without_prefix_accepted(self, monkeypatch):
        """dataset_path without 'datasets/' prefix is accepted if filename exists."""
        pushed: list = []

        class FakeRedis:
            def lpush(self, queue, payload):
                pushed.append(json.loads(payload))

        monkeypatch.setattr(app_module, "get_redis", lambda: FakeRedis())
        monkeypatch.setattr(
            app_module, "_available_datasets", lambda: ["test.jsonl"]
        )
        monkeypatch.setattr(app_module, "_distinct_models", lambda: [])
        monkeypatch.setattr(
            app_module, "_last_nightly_summary", lambda: {"available": False}
        )

        response = app_module.dashboard_new_submit(
            request=_make_request(),
            description="Test no prefix",
            task_type="eval.run",
            model=None,
            dataset_path="test.jsonl",
            evaluator="deterministic",
            judge_model=None,
            scorers=["exact_match"],
            rubric_json=None,
        )

        assert response.status_code == 303
        assert len(pushed) == 1
        assert pushed[0]["inputs"]["dataset_path"] == "test.jsonl"


class TestDatasetRegistration:
    """Tests for Sprint F: GET/POST /dashboard/register."""

    VALID_LINE = '{"id":"x","prompt":"hello","expected":"hello"}'

    def test_register_page_returns_200(self, monkeypatch):
        """GET /dashboard/register should render the registration form."""
        monkeypatch.setattr(app_module, "_last_nightly_summary", lambda: {"available": False})
        request = _make_request()
        response = app_module.dashboard_register(request=request)
        assert response.status_code == 200
        body = response.body.decode("utf-8")
        assert "Register Dataset" in body

    def test_register_empty_name_returns_422(self, monkeypatch):
        """Empty dataset name should return 422."""
        monkeypatch.setattr(app_module, "_last_nightly_summary", lambda: {"available": False})
        response = app_module.dashboard_register_submit(
            _make_request(), name="", content=self.VALID_LINE
        )
        assert response.status_code == 422
        body = response.body.decode("utf-8")
        assert "name is required" in body

    def test_register_duplicate_returns_422(self, monkeypatch):
        """Duplicate dataset name should return 422."""
        monkeypatch.setattr(app_module, "_available_datasets", lambda: ["dup.jsonl"])
        monkeypatch.setattr(app_module, "_last_nightly_summary", lambda: {"available": False})
        response = app_module.dashboard_register_submit(
            _make_request(), name="dup", content=self.VALID_LINE
        )
        assert response.status_code == 422
        body = response.body.decode("utf-8")
        assert "already exists" in body

    def test_register_invalid_jsonl_returns_422(self, monkeypatch):
        """Invalid JSONL content should return 422."""
        monkeypatch.setattr(app_module, "_last_nightly_summary", lambda: {"available": False})
        response = app_module.dashboard_register_submit(
            _make_request(), name="new.jsonl", content="not-json\n{\"id\":\"x\",\"prompt\":\"p\"}"
        )
        assert response.status_code == 422
        body = response.body.decode("utf-8")
        assert "invalid JSON" in body

    def test_register_missing_required_keys_returns_422(self, monkeypatch):
        """JSONL missing required keys should return 422."""
        monkeypatch.setattr(app_module, "_last_nightly_summary", lambda: {"available": False})
        response = app_module.dashboard_register_submit(
            _make_request(), name="new.jsonl", content='{"id":"x","prompt":"p"}'
        )
        assert response.status_code == 422
        body = response.body.decode("utf-8")
        assert "missing keys" in body

    def test_register_path_traversal_returns_422(self, monkeypatch):
        """Path traversal in filename should be rejected."""
        monkeypatch.setattr(app_module, "_last_nightly_summary", lambda: {"available": False})
        response = app_module.dashboard_register_submit(
            _make_request(), name="../../../etc/passwd.jsonl", content=self.VALID_LINE
        )
        assert response.status_code == 422
        body = response.body.decode("utf-8")
        assert "Invalid dataset name" in body

    def test_register_backslash_in_name_returns_422(self, monkeypatch):
        """Backslash in filename should be rejected."""
        monkeypatch.setattr(app_module, "_last_nightly_summary", lambda: {"available": False})
        response = app_module.dashboard_register_submit(
            _make_request(), name="foo\\bar.jsonl", content=self.VALID_LINE
        )
        assert response.status_code == 422

    def test_register_empty_content_returns_422(self, monkeypatch):
        """Empty dataset content should return 422."""
        monkeypatch.setattr(app_module, "_last_nightly_summary", lambda: {"available": False})
        response = app_module.dashboard_register_submit(
            _make_request(), name="empty.jsonl", content=""
        )
        assert response.status_code == 422
        body = response.body.decode("utf-8")
        assert "required" in body

    def test_register_valid_jsonl_saves_and_redirects(self, monkeypatch, tmp_path):
        """Valid JSONL should be written to SHARED_DIR/datasets/ and redirect to /dashboard/new."""
        ds_dir = tmp_path / "datasets"
        ds_dir.mkdir()
        monkeypatch.setattr(app_module, "SHARED_DIR", tmp_path)
        monkeypatch.setattr(app_module, "_last_nightly_summary", lambda: {"available": False})
        content = '{"id":"a","prompt":"hi","expected":"there"}\n{"id":"b","prompt":"yo","expected":"ya"}'

        response = app_module.dashboard_register_submit(
            _make_request(), name="newtest.jsonl", content=content
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard/new"
        saved = (ds_dir / "newtest.jsonl").read_text()
        assert "a" in saved
        assert "b" in saved
        assert saved.endswith("\n")

    def test_register_auto_append_jsonl_extension(self, monkeypatch, tmp_path):
        """Should auto-append .jsonl if the user omits it."""
        ds_dir = tmp_path / "datasets"
        ds_dir.mkdir()
        monkeypatch.setattr(app_module, "SHARED_DIR", tmp_path)
        monkeypatch.setattr(app_module, "_last_nightly_summary", lambda: {"available": False})

        response = app_module.dashboard_register_submit(
            _make_request(), name="auto_test", content=self.VALID_LINE
        )

        assert response.status_code == 303
        saved = (ds_dir / "auto_test.jsonl").read_text()
        assert "x" in saved
