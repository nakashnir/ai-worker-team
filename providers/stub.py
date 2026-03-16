"""
providers/stub.py
Stub providers — no API keys, no network calls.
"""

from __future__ import annotations

from .base import Provider


class EchoExpectedProvider(Provider):
    """
    Returns expected verbatim (or "N/A" when expected is None).
    Guarantees exact_match = 1 for every sample that has an expected value.
    Registered model name: stub.echo_expected
    """

    def generate(self, prompt: str, expected: str | None = None) -> str:
        return expected if expected is not None else "N/A"


class EchoPromptProvider(Provider):
    """
    Returns the prompt verbatim.
    Useful for confirming scorers distinguish output from expected.
    Registered model name: stub.echo_prompt
    """

    def generate(self, prompt: str, expected: str | None = None) -> str:
        return prompt
