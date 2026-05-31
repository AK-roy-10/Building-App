"""Anthropic Claude provider. Degrades to mock if no key configured."""
from __future__ import annotations
import os
from typing import Optional

from ..base import LLMProvider, LLMResult, ProviderCard, register_provider


class AnthropicProvider:
    card = ProviderCard(
        code="anthropic", name="Anthropic Claude",
        requires_api_key=True, supports_embeddings=False, supports_json_mode=True,
        supports_tools=True, self_hosted=False,
        homepage="https://console.anthropic.com",
        notes="Claude 3.5 Sonnet, Claude 3 Haiku. Configure ANTHROPIC_API_KEY in env.",
    )

    def _key(self) -> str:
        return os.environ.get("ANTHROPIC_API_KEY", "")

    def analyze(self, *, model: str, context: dict, prompt: str,
                params: Optional[dict] = None) -> LLMResult:
        key = self._key()
        if not key:
            from .mock import MockProvider
            res = MockProvider().analyze(model=model, context=context, prompt=prompt)
            res.rationale = "[anthropic: no API key; using mock] " + res.rationale
            return res
        import httpx, json
        name = {
            "claude-3-5-sonnet": "claude-3-5-sonnet-latest",
            "claude-3-haiku": "claude-3-haiku-20240307",
        }.get(model, model)
        system = ("You are a markets analyst. You MAY NOT execute trades, call tools, "
                  "or provide personalized financial advice. Summarize the analytical "
                  "context and classify it as bullish/bearish/neutral.")
        user = f"Context:\n{json.dumps(context)[:4000]}\n\nQuestion:\n{prompt}"
        try:
            r = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                         "Content-Type": "application/json"},
                json={"model": name, "max_tokens": (params or {}).get("max_tokens", 512),
                      "system": system,
                      "messages": [{"role": "user", "content": user}]},
                timeout=20.0,
            )
            r.raise_for_status()
            data = r.json()
            text = "".join(p.get("text", "") for p in data.get("content", []))
            low = text.lower()
            cls = "bullish" if "bullish" in low else "bearish" if "bearish" in low else "neutral"
            usage = data.get("usage", {})
            return LLMResult(model=name, provider="anthropic", rationale=text, classification=cls,
                             tokens_in=usage.get("input_tokens", 0),
                             tokens_out=usage.get("output_tokens", 0), raw=data)
        except Exception as e:
            from .mock import MockProvider
            res = MockProvider().analyze(model=model, context=context, prompt=prompt)
            res.rationale = f"[anthropic fallback: {e}] " + res.rationale
            return res

    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        from .mock import MockProvider
        return MockProvider().embed(texts, model=model)


register_provider(AnthropicProvider())
