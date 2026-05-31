"""Deterministic mock LLM. Always available, no API key needed."""
from __future__ import annotations
import hashlib
from typing import Optional

from ..base import LLMProvider, LLMResult, ProviderCard, register_provider


class MockProvider:
    card = ProviderCard(
        code="mock", name="Mock (offline)", requires_api_key=False,
        supports_embeddings=True, supports_json_mode=True, supports_tools=False,
        self_hosted=False, notes="Always-on deterministic fallback. Not for production.",
    )

    def analyze(self, *, model: str, context: dict, prompt: str,
                params: Optional[dict] = None) -> LLMResult:
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
        return LLMResult(
            model=model, provider="mock", rationale=text, classification=cls,
            tokens_in=len(prompt) // 4, tokens_out=len(text) // 4,
        )

    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        out = []
        for t in texts:
            h = hashlib.sha256(t.encode()).digest()
            out.append([(b / 255.0) for b in h[:32]])
        return out


register_provider(MockProvider())
