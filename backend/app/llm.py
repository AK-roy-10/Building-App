"""Back-compat shim. The real LLM stack now lives in `app.llms.*`.

This file is kept so existing imports (`from .llm import get_llm`) still work.
The shape of `LLMResult` is preserved; new code should use `app.llms.complete`.

CRITICAL DESIGN RULE: the LLM is given READ-ONLY analytical context and asked
for narrative explanations / classifications only. It is NEVER given a tool
to place trades. Trade proposals are always emitted by the deterministic
strategy code, not by the LLM.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from . import llms as _llms


@dataclass
class LLMResult:
    """Legacy result shape. New code should use `app.llms.LLMResult`."""
    model: str
    rationale: str
    classification: str
    tokens_in: int = 0
    tokens_out: int = 0


class LLMClient:
    """Legacy interface, retained for back-compat with imports."""

    def analyze(self, *, model: str, context: dict, prompt: str) -> LLMResult:
        res = _llms.complete(model=model, context=context, prompt=prompt)
        return LLMResult(model=res.model, rationale=res.rationale,
                         classification=res.classification,
                         tokens_in=res.tokens_in, tokens_out=res.tokens_out)


class MockLLM(LLMClient):
    pass


class OpenAILLM(LLMClient):
    def __init__(self, api_key: str = "", default_model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.default_model = default_model


_client: Optional[LLMClient] = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client

