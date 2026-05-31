"""Google Gemini provider (stub). Degrades to mock if no key configured."""
from __future__ import annotations
import os
from typing import Optional

from ..base import LLMProvider, LLMResult, ProviderCard, register_provider


class GeminiProvider:
    card = ProviderCard(
        code="gemini", name="Google Gemini",
        requires_api_key=True, supports_embeddings=True, supports_json_mode=True,
        supports_tools=True, self_hosted=False,
        homepage="https://aistudio.google.com",
        notes="Gemini 1.5 Pro / Flash. Configure GOOGLE_API_KEY in env.",
    )

    def _key(self) -> str:
        return os.environ.get("GOOGLE_API_KEY", "")

    def analyze(self, *, model: str, context: dict, prompt: str,
                params: Optional[dict] = None) -> LLMResult:
        key = self._key()
        if not key:
            from .mock import MockProvider
            res = MockProvider().analyze(model=model, context=context, prompt=prompt)
            res.rationale = "[gemini: no API key; using mock] " + res.rationale
            return res
        import httpx, json
        name = {"gemini-1.5-pro": "gemini-1.5-pro-latest"}.get(model, model)
        system = ("You are a markets analyst. Do not execute trades or give personalized "
                  "financial advice. Classify as bullish/bearish/neutral.")
        user = f"Context:\n{json.dumps(context)[:4000]}\n\nQuestion:\n{prompt}"
        try:
            r = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{name}:generateContent?key={key}",
                headers={"Content-Type": "application/json"},
                json={"contents": [{"role": "user",
                                    "parts": [{"text": system + "\n\n" + user}]}]},
                timeout=20.0,
            )
            r.raise_for_status()
            data = r.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            low = text.lower()
            cls = "bullish" if "bullish" in low else "bearish" if "bearish" in low else "neutral"
            return LLMResult(model=name, provider="gemini", rationale=text,
                             classification=cls, raw=data)
        except Exception as e:
            from .mock import MockProvider
            res = MockProvider().analyze(model=model, context=context, prompt=prompt)
            res.rationale = f"[gemini fallback: {e}] " + res.rationale
            return res

    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        from .mock import MockProvider
        return MockProvider().embed(texts, model=model)


register_provider(GeminiProvider())
