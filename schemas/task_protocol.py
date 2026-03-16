"""
schemas/task_protocol.py
Shared Pydantic models for the AI Worker Team task protocol.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    queued  = "queued"
    running = "running"
    done    = "done"
    failed  = "failed"


class Task(BaseModel):
    task_id:     str
    description: str
    task_type:   str = "research.stub"
    inputs:      Dict[str, Any] = Field(default_factory=dict)
    created_at:  str                             # ISO-8601 UTC string
    status:      TaskStatus = TaskStatus.queued


class TaskResult(BaseModel):
    task_id:      str
    status:       TaskStatus
    output_path:  Optional[str] = None
    error:        Optional[str] = None
    completed_at: Optional[str] = None


def task_from_json(raw: str) -> Task:
    return Task.model_validate_json(raw)


def result_from_json(raw: str) -> TaskResult:
    return TaskResult.model_validate_json(raw)


def export_schemas() -> Dict[str, Any]:
    return {
        "Task":       Task.model_json_schema(),
        "TaskResult": TaskResult.model_json_schema(),
    }


if __name__ == "__main__":
    print(json.dumps(export_schemas(), indent=2))
