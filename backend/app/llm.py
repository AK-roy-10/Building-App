"""LLM abstraction. Default is a deterministic mock so the system runs without API keys.

CRITICAL DESIGN RULE: the LLM is given READ-ONLY analytical context and asked for
narrative explanations / classifications only. It is NEVER given a tool to place trades.
Trade proposals are always emitted by the deterministic strategy code, not by the LLM.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .config import get_settings


@dataclass
class LLMResult:
    model: str
    rationale: str
    classification: str  # bullish / bearish / neutral
    tokens_in: int = 0
    tokens_out: int = 0


class LLMClient:
    def analyze(self, *, model: str, context: dict, prompt: str) -> LLMResult:
        raise NotImplementedError


class MockLLM(LLMClient):
    def analyze(self, *, model: str, context: dict, prompt: str) -> LLMResult:
        signal = (context.get("signal") or "").lower()
        symbol = context.get("symbol", "?")
        last = context.get("last_price", 0.0)
        change = context.get("pct_change", 0.0)
        if signal in ("buy", "bullish"):
            cls = "bullish"
            text = (f"{symbol} shows bullish momentum: last={last:.2f}, "
                    f"recent change={change:+.2%}. Strategy thresholds were met. "
                    f"This is an automated analytical note, not financial advice.")
        elif signal in ("sell", "bearish"):
            cls = "bearish"
            text = (f"{symbol} shows bearish/mean-reversion conditions: last={last:.2f}, "
                    f"change={change:+.2%}. Strategy thresholds met for exit/short. "
                    f"Not financial advice.")
        else:
            cls = "neutral"
            text = (f"{symbol}: no decisive signal at last={last:.2f}, change={change:+.2%}. "
                    f"No proposal generated. Not financial advice.")
        return LLMResult(model=model, rationale=text, classification=cls,
                         tokens_in=len(prompt) // 4, tokens_out=len(text) // 4)


class OpenAILLM(LLMClient):
    def __init__(self, api_key: str, default_model: str):
        self.api_key = api_key
        self.default_model = default_model

    def analyze(self, *, model: str, context: dict, prompt: str) -> LLMResult:
        # Lazy import to keep dep optional
        import httpx, json
        model_name = self.default_model if model in ("gpt-small", "gpt-large", "openai") else model
        system = ("You are a markets analyst. You MAY NOT execute trades, call tools, "
                  "or provide personalized financial advice. Summarize the analytical "
                  "context the user provides and classify it as bullish/bearish/neutral.")
        user = f"Context:\n{json.dumps(context)[:4000]}\n\nQuestion:\n{prompt}"
        try:
            r = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"******", "Content-Type": "application/json"},
                json={"model": model_name, "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ], "temperature": 0.2},
                timeout=20.0,
            )
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"]
            cls = "neutral"
            low = text.lower()
            if "bullish" in low: cls = "bullish"
            elif "bearish" in low: cls = "bearish"
            usage = data.get("usage", {})
            return LLMResult(model=model_name, rationale=text, classification=cls,
                             tokens_in=usage.get("prompt_tokens", 0),
                             tokens_out=usage.get("completion_tokens", 0))
        except Exception as e:
            # Fail safe: degrade to mock so the agent doesn't break trading flow.
            mock = MockLLM().analyze(model=model, context=context, prompt=prompt)
            mock.rationale = f"[LLM fallback due to error: {e}] " + mock.rationale
            return mock


_client: Optional[LLMClient] = None


def get_llm() -> LLMClient:
    global _client
    if _client is not None:
        return _client
    s = get_settings()
    if s.openai_api_key:
        _client = OpenAILLM(s.openai_api_key, s.openai_model)
    else:
        _client = MockLLM()
    return _client
