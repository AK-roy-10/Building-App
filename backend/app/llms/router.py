"""High-level router. Picks the right provider + model for a task and forwards
the call. Falls back to the mock provider if the requested provider is not
configured (no API key, etc.), so the system never crashes mid-pipeline.
"""
from __future__ import annotations
from typing import Optional

from .base import LLMResult, get_provider
from .models import get_model, get_default_model


def _resolve(model_id: Optional[str]) -> tuple[str, str]:
    """Return (provider_code, model_name_for_provider) for a catalog model id.

    For unknown ids, fall back to mock so the runtime keeps working.
    """
    if not model_id:
        m = get_default_model()
        return m.provider, m.id
    try:
        m = get_model(model_id)
        return m.provider, m.id
    except KeyError:
        # Could be a raw provider model name (e.g. "claude-3-opus-20240229");
        # we send it through "mock" to keep the pipeline alive but surface
        # the unknown id in rationale.
        return "mock", model_id


def complete(*, model: str, context: dict, prompt: str,
             params: Optional[dict] = None) -> LLMResult:
    provider_code, model_name = _resolve(model)
    try:
        provider = get_provider(provider_code)
    except KeyError:
        provider = get_provider("mock")
        model_name = "mock"
    try:
        return provider.analyze(model=model_name, context=context, prompt=prompt, params=params)
    except Exception as e:
        # Final safety net: never break the agent pipeline because the LLM failed.
        mock = get_provider("mock").analyze(model="mock", context=context, prompt=prompt)
        mock.rationale = f"[LLM fallback ({provider_code}) due to error: {e}] " + mock.rationale
        return mock


def embed(texts: list[str], *, model: str) -> list[list[float]]:
    provider_code, model_name = _resolve(model)
    try:
        return get_provider(provider_code).embed(texts, model=model_name)
    except Exception:
        # Mock embeddings: fixed-size deterministic hashing → vector.
        import hashlib
        out = []
        for t in texts:
            h = hashlib.sha256(t.encode()).digest()
            out.append([(h[i] / 255.0) for i in range(min(32, len(h)))])
        return out
