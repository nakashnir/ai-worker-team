"""
providers/openai.py
OpenAI chat-completion provider.

Only instantiated when OPENAI_API_KEY is set in the environment.
Model name convention: openai:<model_id>  e.g. openai:gpt-4o-mini

The 'openai' package is NOT pinned in the default Dockerfile.
To enable: add 'openai>=1.0' to workers/Dockerfile pip install block.
"""

from __future__ import annotations

import os

from .base import Provider


class OpenAIProvider(Provider):
    """
    Wraps openai.OpenAI chat completions (v1 SDK).
    The bare model id is passed in (prefix "openai:" already stripped).
    """

    def __init__(self, model_id: str) -> None:
        try:
            import openai  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "openai package is not installed. "
                "Add 'openai>=1.0' to workers/Dockerfile to use OpenAI models."
            ) from exc

        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY is not set")

        self._client = openai.OpenAI(api_key=api_key)
        self._model  = model_id

    def generate(self, prompt: str, expected: str | None = None) -> str:
        response = self._client.chat.completions.create(
            model     = self._model,
            messages  = [{"role": "user", "content": prompt}],
            max_tokens = 512,
        )
        return (response.choices[0].message.content or "").strip()
