"""Local Ollama provider for self-hosted open models (FinGPT, Mistral-Finance, Llama-3 ...).

Talks to a locally-running Ollama daemon over HTTP. If the daemon isn't
reachable, degrades to the mock provider so the agent pipeline never breaks.
"""
from __future__ import annotations
import os
from typing import Optional

from ..base import LLMProvider, LLMResult, ProviderCard, register_provider


class OllamaProvider:
    card = ProviderCard(
        code="ollama", name="Ollama (local)",
        requires_api_key=False, supports_embeddings=True, supports_json_mode=True,
        supports_tools=False, self_hosted=True,
        homepage="https://ollama.com",
        notes="Self-hosted: run `ollama serve`, then `ollama pull llama3:8b` etc.",
    )

    def _base(self) -> str:
        return os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")

    def analyze(self, *, model: str, context: dict, prompt: str,
                params: Optional[dict] = None) -> LLMResult:
        import httpx, json
        # Map catalog ids → Ollama model tags. Users can pull custom finance
        # fine-tunes by their HF id and reference the local tag.
        name = {
            "fingpt-llama3-8b": "fingpt-llama3:8b",
            "mistral-finance-7b": "mistral-finance:7b",
        }.get(model, model)
        system = ("You are a markets analyst. Do not execute trades or give personalized "
                  "financial advice. Classify as bullish/bearish/neutral.")
        user = f"Context:\n{json.dumps(context)[:4000]}\n\nQuestion:\n{prompt}"
        try:
            r = httpx.post(
                self._base() + "/api/chat",
                json={"model": name, "stream": False,
                      "messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": user}],
                      "options": {"temperature": (params or {}).get("temperature", 0.2)}},
                timeout=60.0,
            )
            r.raise_for_status()
            data = r.json()
            text = data.get("message", {}).get("content", "")
            low = text.lower()
            cls = "bullish" if "bullish" in low else "bearish" if "bearish" in low else "neutral"
            return LLMResult(model=name, provider="ollama", rationale=text,
                             classification=cls, raw=data)
        except Exception as e:
            from .mock import MockProvider
            res = MockProvider().analyze(model=model, context=context, prompt=prompt)
            res.rationale = f"[ollama fallback ({name}): {e}] " + res.rationale
            return res

    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        import httpx
        try:
            out: list[list[float]] = []
            for t in texts:
                r = httpx.post(self._base() + "/api/embeddings",
                               json={"model": model, "prompt": t}, timeout=30.0)
                r.raise_for_status()
                out.append(r.json().get("embedding", []))
            return out
        except Exception:
            from .mock import MockProvider
            return MockProvider().embed(texts, model=model)


register_provider(OllamaProvider())
