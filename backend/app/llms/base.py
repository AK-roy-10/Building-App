"""LLM provider interface + registry.

Critical invariant (inherited from app/llm.py): the LLM is an *analyst*. It
NEVER receives tools that touch a broker. All trade decisions remain in the
deterministic strategy + risk-engine path.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable


@dataclass
class LLMResult:
    model: str
    provider: str
    rationale: str
    classification: str = "neutral"   # bullish / bearish / neutral
    tokens_in: int = 0
    tokens_out: int = 0
    raw: dict = field(default_factory=dict)


@dataclass
class ProviderCard:
    code: str
    name: str
    requires_api_key: bool = True
    supports_embeddings: bool = False
    supports_json_mode: bool = False
    supports_tools: bool = False
    self_hosted: bool = False
    homepage: str = ""
    notes: str = ""


@runtime_checkable
class LLMProvider(Protocol):
    card: ProviderCard

    def analyze(self, *, model: str, context: dict, prompt: str,
                params: Optional[dict] = None) -> LLMResult: ...

    def embed(self, texts: list[str], *, model: str) -> list[list[float]]: ...


_REGISTRY: dict[str, LLMProvider] = {}


def register_provider(provider: LLMProvider) -> None:
    _REGISTRY[provider.card.code] = provider


def get_provider(code: str) -> LLMProvider:
    if code not in _REGISTRY:
        raise KeyError(f"Unknown LLM provider: {code}. Available: {list(_REGISTRY)}")
    return _REGISTRY[code]


def list_providers() -> list[dict]:
    return [p.card.__dict__ for p in _REGISTRY.values()]
