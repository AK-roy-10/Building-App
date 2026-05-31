"""OpenAI provider (HTTP). Degrades to mock if no key configured."""
from __future__ import annotations
from typing import Optional

from ..base import LLMProvider, LLMResult, ProviderCard, register_provider
from ...config import get_settings


class OpenAIProvider:
    card = ProviderCard(
        code="openai", name="OpenAI",
        requires_api_key=True, supports_embeddings=True, supports_json_mode=True,
        supports_tools=True, self_hosted=False,
        homepage="https://platform.openai.com",
        notes="GPT-4o, GPT-4o-mini, embeddings. Configure OPENAI_API_KEY in env.",
    )

    def _key(self) -> str:
        return get_settings().openai_api_key

    def analyze(self, *, model: str, context: dict, prompt: str,
                params: Optional[dict] = None) -> LLMResult:
        key = self._key()
        if not key:
            from .mock import MockProvider
            res = MockProvider().analyze(model=model, context=context, prompt=prompt)
            res.rationale = "[openai: no API key; using mock] " + res.rationale
            return res
        import httpx, json
        # Resolve catalog id aliases to real OpenAI model names
        name = {
            "gpt-large": "gpt-4o",
            "gpt-small": "gpt-4o-mini",
            "openai": "gpt-4o-mini",
        }.get(model, model)
        system = ("You are a markets analyst. You MAY NOT execute trades, call tools, "
                  "or provide personalized financial advice. Summarize the analytical "
                  "context the user provides and classify it as bullish/bearish/neutral.")
        user = f"Context:\n{json.dumps(context)[:4000]}\n\nQuestion:\n{prompt}"
        try:
            r = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"******", "Content-Type": "application/json"},
                json={"model": name, "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ], "temperature": (params or {}).get("temperature", 0.2)},
                timeout=20.0,
            )
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"]
            low = text.lower()
            cls = "bullish" if "bullish" in low else "bearish" if "bearish" in low else "neutral"
            usage = data.get("usage", {})
            return LLMResult(model=name, provider="openai", rationale=text, classification=cls,
                             tokens_in=usage.get("prompt_tokens", 0),
                             tokens_out=usage.get("completion_tokens", 0), raw=data)
        except Exception as e:
            from .mock import MockProvider
            res = MockProvider().analyze(model=model, context=context, prompt=prompt)
            res.rationale = f"[openai fallback: {e}] " + res.rationale
            return res

    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        key = self._key()
        if not key:
            from .mock import MockProvider
            return MockProvider().embed(texts, model=model)
        import httpx
        try:
            r = httpx.post("https://api.openai.com/v1/embeddings",
                           headers={"Authorization": f"******",
                                    "Content-Type": "application/json"},
                           json={"model": model or "text-embedding-3-small", "input": texts},
                           timeout=30.0)
            r.raise_for_status()
            return [d["embedding"] for d in r.json()["data"]]
        except Exception:
            from .mock import MockProvider
            return MockProvider().embed(texts, model=model)


register_provider(OpenAIProvider())
