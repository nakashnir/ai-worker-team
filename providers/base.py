"""
providers/base.py
Abstract base class for all model providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Provider(ABC):
    """
    Minimal synchronous provider interface.
    All subclasses must implement generate().
    """

    @abstractmethod
    def generate(self, prompt: str, expected: str | None = None) -> str:
        """
        Generate an output string for the given prompt.

        Args:
            prompt:   Input prompt string.
            expected: Reference answer. Real providers MUST ignore this.
                      Stub providers may use it.

        Returns:
            Model output string (never None).
        """
