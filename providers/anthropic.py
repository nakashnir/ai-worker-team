"""
providers/anthropic.py
Production-hardened Anthropic provider — Ticket A6.

Configuration via environment variables (all optional; built-in defaults shown):
  ANTHROPIC_TIMEOUT_SECS       30.0   — per-request timeout in seconds
  ANTHROPIC_MAX_RETRIES        2      — max retry attempts after first failure
  ANTHROPIC_BACKOFF_BASE_SECS  1.0    — base sleep seconds; doubles each retry

Retry policy:
  Retryable    : HTTP 429, 500, 502, 503, 504; connection errors; timeouts
  Non-retryable: HTTP 401, 403, 404 → raises ProviderFatalError immediately
  Unknown 4xx  : treated as non-retryable → raises ProviderFatalError

Typed exceptions:
  ProviderKeyMissingError — ANTHROPIC_API_KEY absent
                            → resolve_provider() falls back to stub (no task failure)
  ProviderFatalError      — non-retryable API error (carries .http_status)
                            → eval.run marks task failed, still writes all artifacts

Return type of generate_with_meta():
  (text: str, meta: ProviderMeta)

ProviderMeta fields:
  model          str | None  — model id echoed by API response
  stop_reason    str | None
  input_tokens   int | None
  output_tokens  int | None
  retries_count  int         — 0 means first attempt succeeded
  elapsed_ms     int         — wall-clock ms for the entire call (all attempts)
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from .base import Provider


# ─────────────────────────────────────────────
# Typed exceptions
# ─────────────────────────────────────────────

class ProviderKeyMissingError(RuntimeError):
    """
    Raised when ANTHROPIC_API_KEY is absent.
    Caught by resolve_provider() which falls back to EchoExpectedProvider.
    The eval task does NOT fail — it completes with stub output.
    """


class ProviderFatalError(RuntimeError):
    """
    Non-retryable API error (401, 403, 404, unexpected 4xx).
    Caught in handle_eval_run(); task is marked failed but all file
    artifacts (eval_results.jsonl, eval_report.md, run.json) are still written.

    Attributes:
        http_status  int | None  — HTTP status code when available
    """
    def __init__(self, message: str, http_status: int | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status


# ─────────────────────────────────────────────
# Return-value dataclass
# ─────────────────────────────────────────────

@dataclass
class ProviderMeta:
    model:         str | None = None
    stop_reason:   str | None = None
    input_tokens:  int | None = None
    output_tokens: int | None = None
    retries_count: int        = 0
    elapsed_ms:    int        = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "model":         self.model,
            "stop_reason":   self.stop_reason,
            "input_tokens":  self.input_tokens,
            "output_tokens": self.output_tokens,
            "retries_count": self.retries_count,
            "elapsed_ms":    self.elapsed_ms,
        }


# ─────────────────────────────────────────────
# Provider implementation
# ─────────────────────────────────────────────

class AnthropicProvider(Provider):
    """
    Wraps anthropic.Anthropic.messages.create().
    model_id is the bare model string; the "anthropic:" prefix is stripped
    by resolve_provider() before this class is instantiated.
    """

    # HTTP status codes handled differently
    _RETRYABLE_STATUSES  = frozenset({429, 500, 502, 503, 504})
    _FATAL_STATUSES      = frozenset({401, 403, 404})

    def __init__(self, model_id: str) -> None:
        try:
            import anthropic as _sdk  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "anthropic package not installed. "
                "Add 'anthropic>=0.40' to workers/Dockerfile."
            ) from exc

        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise ProviderKeyMissingError(
                "ANTHROPIC_API_KEY is not set; cannot instantiate AnthropicProvider"
            )

        self._sdk    = _sdk
        self._client = _sdk.Anthropic(api_key=api_key)
        self._model  = model_id

        # Runtime config — env vars with built-in defaults
        self._timeout     = float(os.environ.get("ANTHROPIC_TIMEOUT_SECS",      "30.0"))
        self._max_retries = int(float(os.environ.get("ANTHROPIC_MAX_RETRIES",   "2")))
        self._backoff     = float(os.environ.get("ANTHROPIC_BACKOFF_BASE_SECS", "1.0"))

    # ── Provider base-class interface ─────────────────────────────

    def generate(
        self,
        prompt:     str,
        expected:   str | None = None,   # real providers ignore expected
        system:     str | None = None,
        max_tokens: int        = 512,
    ) -> str:
        text, _ = self.generate_with_meta(
            prompt=prompt, system=system, max_tokens=max_tokens
        )
        return text

    # ── Extended interface (used by eval.run for telemetry) ───────

    def generate_with_meta(
        self,
        prompt:     str,
        system:     str | None = None,
        max_tokens: int        = 512,
    ) -> tuple[str, ProviderMeta]:
        """
        Call the Anthropic messages API with selective retry and backoff.

        Raises:
            ProviderFatalError  — on 401 / 403 / 404 (no retry; propagates to eval.run)
            RuntimeError        — if all retryable attempts are exhausted
        """
        kwargs: dict[str, Any] = {
            "model":      self._model,
            "max_tokens": max_tokens,
            "messages":   [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        max_attempts  = self._max_retries + 1   # retries=2 → up to 3 attempts
        retries_count = 0
        last_exc: Exception | None = None
        wall_start = time.monotonic()

        for attempt in range(1, max_attempts + 1):
            try:
                response = self._client.messages.create(
                    **kwargs,
                    timeout=self._timeout,
                )
                elapsed_ms = int((time.monotonic() - wall_start) * 1000)
                return self._build_result(response, retries_count, elapsed_ms)

            except self._sdk.APIStatusError as exc:
                status = exc.status_code

                # Fatal — do not retry; propagate immediately
                if status in self._FATAL_STATUSES:
                    elapsed_ms = int((time.monotonic() - wall_start) * 1000)
                    raise ProviderFatalError(
                        f"Anthropic API returned HTTP {status} for model "
                        f"{self._model!r}: {exc.message}",
                        http_status=status,
                    ) from exc

                # Retryable status
                if status in self._RETRYABLE_STATUSES:
                    last_exc = exc
                    if attempt < max_attempts:
                        retries_count += 1
                        time.sleep(self._backoff * (2 ** (attempt - 1)))
                    continue

                # Unknown status code — treat as fatal
                raise ProviderFatalError(
                    f"Anthropic API returned unexpected HTTP {status}: {exc.message}",
                    http_status=status,
                ) from exc

            except (
                self._sdk.APIConnectionError,
                self._sdk.APITimeoutError,
            ) as exc:
                # Network / timeout — retryable
                last_exc = exc
                if attempt < max_attempts:
                    retries_count += 1
                    time.sleep(self._backoff * (2 ** (attempt - 1)))
                continue

        # All attempts exhausted on retryable errors
        elapsed_ms = int((time.monotonic() - wall_start) * 1000)
        raise RuntimeError(
            f"Anthropic API failed after {max_attempts} attempt(s) "
            f"(retries={retries_count}, elapsed_ms={elapsed_ms}): {last_exc}"
        ) from last_exc

    # ── Private helpers ───────────────────────────────────────────

    def _build_result(
        self, response: Any, retries_count: int, elapsed_ms: int
    ) -> tuple[str, ProviderMeta]:
        usage = getattr(response, "usage", None)
        meta  = ProviderMeta(
            model         = getattr(response, "model",       None),
            stop_reason   = getattr(response, "stop_reason", None),
            input_tokens  = getattr(usage, "input_tokens",  None) if usage else None,
            output_tokens = getattr(usage, "output_tokens", None) if usage else None,
            retries_count = retries_count,
            elapsed_ms    = elapsed_ms,
        )
        return self._extract_text(response), meta

    @staticmethod
    def _extract_text(response: Any) -> str:
        for block in (getattr(response, "content", None) or []):
            if hasattr(block, "text"):
                return block.text.strip()
        return ""
