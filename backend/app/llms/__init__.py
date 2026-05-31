"""LLM registry: providers + finance-tuned model catalog.

Public surface:
    LLMResult, LLMProvider          — interface
    ModelCard                       — catalog entry
    register_provider, get_provider — provider registry
    list_models, get_model, get_default_model
    complete(...)                   — high-level routed call
"""
from .base import LLMResult, LLMProvider, ProviderCard, register_provider, get_provider, list_providers
from .models import ModelCard, list_models, get_model, get_default_model, ModelTask
from .router import complete, embed

# Self-registering providers
from .providers import mock as _mock  # noqa: F401
from .providers import openai_provider as _openai  # noqa: F401
from .providers import anthropic_provider as _anthropic  # noqa: F401
from .providers import gemini_provider as _gemini  # noqa: F401
from .providers import ollama_provider as _ollama  # noqa: F401
from .providers import hf_provider as _hf  # noqa: F401

__all__ = [
    "LLMResult", "LLMProvider", "ProviderCard",
    "register_provider", "get_provider", "list_providers",
    "ModelCard", "ModelTask", "list_models", "get_model", "get_default_model",
    "complete", "embed",
]
