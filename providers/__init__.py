"""
providers/__init__.py
Provider factory.

resolve_provider(model) -> (Provider, fallback_reason | None)

Routing:
  stub.echo_expected          -> EchoExpectedProvider()
  stub.echo_prompt            -> EchoPromptProvider()
  openai:<model_id>           -> OpenAIProvider(model_id)   — needs OPENAI_API_KEY
  anthropic:<model_id>        -> AnthropicProvider(model_id) — needs ANTHROPIC_API_KEY
  <anything else>             -> EchoExpectedProvider() + fallback_reason

Fallback contract:
  A missing env var, missing package, or unknown model string causes resolve_provider
  to return (EchoExpectedProvider(), "<reason string>") instead of raising.
  The worker logs the reason in run.json summary and continues — the task never fails
  due to a missing provider key.
"""

from __future__ import annotations

import os

from .base import Provider
from .stub import EchoExpectedProvider, EchoPromptProvider

__all__ = ["resolve_provider"]

# Named stub models that require no env var check
_STUB_MAP: dict[str, type[Provider]] = {
    "stub.echo_expected": EchoExpectedProvider,
    "stub.echo_prompt":   EchoPromptProvider,
}


def resolve_provider(model: str) -> tuple[Provider, str | None]:
    """
    Return (provider_instance, fallback_reason).

    fallback_reason is None  -> requested provider was used as-is.
    fallback_reason is a str -> fell back to EchoExpectedProvider; reason explains why.
    """
    # ── Named stubs ───────────────────────────────────────────────
    if model in _STUB_MAP:
        return _STUB_MAP[model](), None

    # ── OpenAI ───────────────────────────────────────────────────
    if model.startswith("openai:"):
        model_id = model[len("openai:"):]
        missing  = _missing_key("OPENAI_API_KEY", "openai", model)
        if missing:
            return EchoExpectedProvider(), missing
        try:
            from .openai import OpenAIProvider  # noqa: PLC0415
            return OpenAIProvider(model_id), None
        except Exception as exc:
            return (
                EchoExpectedProvider(),
                f"OpenAI provider init failed ({exc}); fell back to stub.echo_expected",
            )

    # ── Anthropic ────────────────────────────────────────────────
    if model.startswith("anthropic:"):
        model_id = model[len("anthropic:"):]
        missing  = _missing_key("ANTHROPIC_API_KEY", "anthropic", model)
        if missing:
            return EchoExpectedProvider(), missing
        try:
            from .anthropic import AnthropicProvider  # noqa: PLC0415
            return AnthropicProvider(model_id), None
        except Exception as exc:
            return (
                EchoExpectedProvider(),
                f"Anthropic provider init failed ({exc}); fell back to stub.echo_expected",
            )

    # ── Unknown model → soft fallback (never raise) ───────────────
    return (
        EchoExpectedProvider(),
        f"unknown model {model!r}; fell back to stub.echo_expected",
    )


def _missing_key(env_var: str, provider_name: str, model: str) -> str | None:
    """Return a fallback reason string if env_var is absent, else None."""
    if not os.environ.get(env_var, "").strip():
        return (
            f"{env_var} not set; cannot use {provider_name} model {model!r}; "
            f"fell back to stub.echo_expected"
        )
    return None
