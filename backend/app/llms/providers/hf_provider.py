"""Hugging Face Inference provider (stub).

Useful for community finance fine-tunes (Instruct-FinGPT, FinMA, FinTral,
Finance-Chat) hosted on the HF Inference API or Inference Endpoints.
Degrades to mock if no key is configured.
"""
from __future__ import annotations
import os
from typing import Optional

from ..base import LLMProvider, LLMResult, ProviderCard, register_provider


class HuggingFaceProvider:
    card = ProviderCard(
        code="hugging_face", name="Hugging Face Inference",
        requires_api_key=True, supports_embeddings=True, supports_json_mode=False,
        supports_tools=False, self_hosted=False,
        homepage="https://huggingface.co/inference-api",
        notes="Use for community finance fine-tunes. Configure HF_TOKEN in env.",
    )

    def _key(self) -> str:
        return os.environ.get("HF_TOKEN", "") or os.environ.get("HUGGINGFACEHUB_API_TOKEN", "")

    def _hf_model_id(self, model: str) -> str:
        # Map catalog ids → known HF model ids. Users can also pass a raw HF id.
        return {
            "instruct-fingpt": "FinGPT/fingpt-mt_llama2-7b_lora",
            "finma-7b": "ChanceFocus/finma-7b-full",
            "fintral-7b": "UBC-NLP/FinTral-DPO-v0.1",
            "finance-chat-13b": "AdaptLLM/finance-chat",
            "mixtral-8x7b-instruct": "mistralai/Mixtral-8x7B-Instruct-v0.1",
        }.get(model, model)

    def analyze(self, *, model: str, context: dict, prompt: str,
                params: Optional[dict] = None) -> LLMResult:
        key = self._key()
        if not key:
            from .mock import MockProvider
            res = MockProvider().analyze(model=model, context=context, prompt=prompt)
            res.rationale = "[hugging_face: no token; using mock] " + res.rationale
            return res
        import httpx, json
        hf_id = self._hf_model_id(model)
        system = ("Analyst only. No trades, no advice. Classify bullish/bearish/neutral.")
        user = f"Context:\n{json.dumps(context)[:3000]}\n\nQuestion:\n{prompt}"
        try:
            r = httpx.post(
                f"https://api-inference.huggingface.co/models/{hf_id}",
                headers={"Authorization": f"******"},
                json={"inputs": system + "\n\n" + user,
                      "parameters": {"max_new_tokens": (params or {}).get("max_tokens", 256),
                                     "temperature": (params or {}).get("temperature", 0.2)}},
                timeout=60.0,
            )
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list) and data and "generated_text" in data[0]:
                text = data[0]["generated_text"]
            else:
                text = str(data)
            low = text.lower()
            cls = "bullish" if "bullish" in low else "bearish" if "bearish" in low else "neutral"
            return LLMResult(model=hf_id, provider="hugging_face", rationale=text,
                             classification=cls, raw={"raw": data})
        except Exception as e:
            from .mock import MockProvider
            res = MockProvider().analyze(model=model, context=context, prompt=prompt)
            res.rationale = f"[hugging_face fallback ({hf_id}): {e}] " + res.rationale
            return res

    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        from .mock import MockProvider
        return MockProvider().embed(texts, model=model)


register_provider(HuggingFaceProvider())
