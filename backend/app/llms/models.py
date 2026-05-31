"""Curated catalog of LLM models, with emphasis on finance-tuned options.

Each entry is a `ModelCard` with metadata used by:
  * the UI (model picker shows name / context / cost / license / tags)
  * entitlements (plan can gate by provider, tag or model id)
  * the router (pick the best model for a task type, within allowed list)

The catalog covers general-purpose models AND known finance fine-tunes. Some
finance models (BloombergGPT) are stubbed for completeness — they only become
usable if the user provides credentials / hosting.
"""
from __future__ import annotations
import enum
from dataclasses import dataclass, field
from typing import Optional


class ModelTask(str, enum.Enum):
    chat = "chat"
    news_summary = "news_summary"
    earnings_qna = "earnings_qna"
    chart_commentary = "chart_commentary"
    risk_explanation = "risk_explanation"
    structured = "structured"  # JSON output for programmatic consumption
    embedding = "embedding"


@dataclass
class ModelCard:
    id: str                          # unique within catalog, used as `model_code`
    provider: str                    # provider code (matches ProviderCard.code)
    name: str                        # human-friendly name
    context_tokens: int
    cost_per_1k_in: float            # USD; 0 for self-hosted / free
    cost_per_1k_out: float
    tags: list[str] = field(default_factory=list)
    recommended_tasks: list[str] = field(default_factory=list)
    license: str = ""
    self_hosted: bool = False
    notes: str = ""

    def to_dict(self) -> dict:
        return {**self.__dict__}


# ---------- The catalog ----------
# Tag "finance" marks models that are either finance fine-tunes or
# documented as strong for finance reasoning. Tag "free" marks zero-cost
# options (mock, local Ollama, HF community fine-tunes via free inference).
CATALOG: list[ModelCard] = [
    # --- Mock (always available) ---
    ModelCard(
        id="mock", provider="mock", name="Mock (offline)",
        context_tokens=4096, cost_per_1k_in=0, cost_per_1k_out=0,
        tags=["free", "offline"],
        recommended_tasks=[ModelTask.chat.value, ModelTask.news_summary.value,
                           ModelTask.risk_explanation.value],
        license="N/A",
        notes="Deterministic placeholder used when no provider keys are set.",
    ),

    # --- OpenAI (general purpose, strong finance reasoning) ---
    ModelCard(
        id="gpt-4o", provider="openai", name="GPT-4o",
        context_tokens=128_000, cost_per_1k_in=0.0025, cost_per_1k_out=0.01,
        tags=["general", "finance", "json"],
        recommended_tasks=[t.value for t in ModelTask if t != ModelTask.embedding],
        license="proprietary",
    ),
    ModelCard(
        id="gpt-4o-mini", provider="openai", name="GPT-4o mini",
        context_tokens=128_000, cost_per_1k_in=0.00015, cost_per_1k_out=0.0006,
        tags=["general", "finance", "cheap", "json"],
        recommended_tasks=[ModelTask.chat.value, ModelTask.news_summary.value,
                           ModelTask.structured.value, ModelTask.risk_explanation.value],
        license="proprietary",
    ),
    ModelCard(
        id="text-embedding-3-small", provider="openai", name="Text Embedding 3 small",
        context_tokens=8191, cost_per_1k_in=0.00002, cost_per_1k_out=0,
        tags=["embedding", "cheap"], recommended_tasks=[ModelTask.embedding.value],
        license="proprietary",
    ),

    # --- Anthropic ---
    ModelCard(
        id="claude-3-5-sonnet", provider="anthropic", name="Claude 3.5 Sonnet",
        context_tokens=200_000, cost_per_1k_in=0.003, cost_per_1k_out=0.015,
        tags=["general", "finance", "long-context"],
        recommended_tasks=[ModelTask.chat.value, ModelTask.earnings_qna.value,
                           ModelTask.chart_commentary.value, ModelTask.risk_explanation.value],
        license="proprietary",
    ),
    ModelCard(
        id="claude-3-haiku", provider="anthropic", name="Claude 3 Haiku",
        context_tokens=200_000, cost_per_1k_in=0.00025, cost_per_1k_out=0.00125,
        tags=["general", "cheap", "long-context"],
        recommended_tasks=[ModelTask.chat.value, ModelTask.news_summary.value],
        license="proprietary",
    ),

    # --- Google Gemini ---
    ModelCard(
        id="gemini-1.5-pro", provider="gemini", name="Gemini 1.5 Pro",
        context_tokens=2_000_000, cost_per_1k_in=0.00125, cost_per_1k_out=0.005,
        tags=["general", "finance", "long-context"],
        recommended_tasks=[ModelTask.earnings_qna.value, ModelTask.chart_commentary.value],
        license="proprietary",
    ),

    # --- Finance-tuned, open weights (self-host via Ollama / HF / vLLM) ---
    ModelCard(
        id="fingpt-llama3-8b", provider="ollama", name="FinGPT (Llama-3 8B fine-tune)",
        context_tokens=8192, cost_per_1k_in=0, cost_per_1k_out=0,
        tags=["finance", "open", "self-hosted", "free"],
        recommended_tasks=[ModelTask.news_summary.value, ModelTask.chart_commentary.value,
                           ModelTask.risk_explanation.value],
        license="LLaMA-3 community license",
        self_hosted=True,
        notes="FinGPT project — community finance fine-tunes of LLaMA. Run via Ollama or vLLM.",
    ),
    ModelCard(
        id="instruct-fingpt", provider="hugging_face", name="Instruct-FinGPT",
        context_tokens=4096, cost_per_1k_in=0, cost_per_1k_out=0,
        tags=["finance", "open", "free"],
        recommended_tasks=[ModelTask.news_summary.value, ModelTask.earnings_qna.value],
        license="research",
        self_hosted=True,
        notes="Instruction-tuned variant of FinGPT for finance Q&A.",
    ),
    ModelCard(
        id="finma-7b", provider="hugging_face", name="FinMA 7B",
        context_tokens=4096, cost_per_1k_in=0, cost_per_1k_out=0,
        tags=["finance", "open", "free", "benchmark"],
        recommended_tasks=[ModelTask.earnings_qna.value, ModelTask.structured.value],
        license="research",
        self_hosted=True,
        notes="From the PIXIU benchmark; strong on finance Q&A datasets.",
    ),
    ModelCard(
        id="fintral-7b", provider="hugging_face", name="FinTral 7B",
        context_tokens=8192, cost_per_1k_in=0, cost_per_1k_out=0,
        tags=["finance", "open", "free", "multimodal"],
        recommended_tasks=[ModelTask.chart_commentary.value, ModelTask.earnings_qna.value],
        license="research",
        self_hosted=True,
        notes="Multimodal financial LLM (text + charts).",
    ),
    ModelCard(
        id="finance-chat-13b", provider="hugging_face", name="Finance-Chat (AdaptLLM 13B)",
        context_tokens=4096, cost_per_1k_in=0, cost_per_1k_out=0,
        tags=["finance", "open", "free"],
        recommended_tasks=[ModelTask.chat.value, ModelTask.news_summary.value],
        license="research",
        self_hosted=True,
        notes="AdaptLLM domain-adapted chat model for finance.",
    ),
    ModelCard(
        id="mistral-finance-7b", provider="ollama", name="Mistral 7B (finance fine-tune)",
        context_tokens=8192, cost_per_1k_in=0, cost_per_1k_out=0,
        tags=["finance", "open", "free", "self-hosted"],
        recommended_tasks=[ModelTask.chat.value, ModelTask.news_summary.value],
        license="Apache-2.0 (base)",
        self_hosted=True,
        notes="Community finance fine-tune of Mistral 7B. Run via Ollama.",
    ),

    # --- Proprietary finance models (stubbed) ---
    ModelCard(
        id="bloomberg-gpt", provider="bloomberg", name="BloombergGPT (stub)",
        context_tokens=2048, cost_per_1k_in=0, cost_per_1k_out=0,
        tags=["finance", "proprietary", "stub"],
        recommended_tasks=[ModelTask.earnings_qna.value, ModelTask.risk_explanation.value],
        license="Bloomberg",
        notes="Requires a Bloomberg Terminal / API agreement. Adapter is a stub.",
    ),

    # --- Local default fallback for self-hosted free ---
    ModelCard(
        id="llama3:8b", provider="ollama", name="Llama-3 8B (general)",
        context_tokens=8192, cost_per_1k_in=0, cost_per_1k_out=0,
        tags=["general", "open", "free", "self-hosted"],
        recommended_tasks=[ModelTask.chat.value, ModelTask.news_summary.value],
        license="LLaMA-3 community license",
        self_hosted=True,
    ),

    # --- Together / Groq / others examples ---
    ModelCard(
        id="mixtral-8x7b-instruct", provider="hugging_face", name="Mixtral 8x7B Instruct",
        context_tokens=32_768, cost_per_1k_in=0, cost_per_1k_out=0,
        tags=["general", "open", "free"],
        recommended_tasks=[ModelTask.chat.value, ModelTask.news_summary.value],
        license="Apache-2.0",
        self_hosted=True,
    ),

    # --- Back-compat aliases used by existing tests/entitlements ---
    ModelCard(
        id="gpt-small", provider="openai", name="GPT (small) — alias for gpt-4o-mini",
        context_tokens=128_000, cost_per_1k_in=0.00015, cost_per_1k_out=0.0006,
        tags=["general", "alias", "cheap"],
        recommended_tasks=[ModelTask.chat.value], license="proprietary",
        notes="Back-compat alias retained for existing plan entitlements.",
    ),
    ModelCard(
        id="gpt-large", provider="openai", name="GPT (large) — alias for gpt-4o",
        context_tokens=128_000, cost_per_1k_in=0.0025, cost_per_1k_out=0.01,
        tags=["general", "alias", "finance"],
        recommended_tasks=[ModelTask.chat.value, ModelTask.earnings_qna.value],
        license="proprietary", notes="Back-compat alias retained.",
    ),
]


_BY_ID: dict[str, ModelCard] = {m.id: m for m in CATALOG}


def list_models(*, tag: Optional[str] = None, provider: Optional[str] = None,
                task: Optional[str] = None, free_only: bool = False) -> list[ModelCard]:
    out = []
    for m in CATALOG:
        if tag and tag not in m.tags: continue
        if provider and m.provider != provider: continue
        if task and task not in m.recommended_tasks: continue
        if free_only and (m.cost_per_1k_in or m.cost_per_1k_out): continue
        out.append(m)
    return out


def get_model(model_id: str) -> ModelCard:
    if model_id not in _BY_ID:
        raise KeyError(f"Unknown model id: {model_id}")
    return _BY_ID[model_id]


def get_default_model(*, prefer_tag: Optional[str] = None) -> ModelCard:
    """Default-pick for the runtime when an agent didn't specify."""
    if prefer_tag:
        candidates = list_models(tag=prefer_tag, free_only=True)
        if candidates:
            return candidates[0]
    return _BY_ID["mock"]
