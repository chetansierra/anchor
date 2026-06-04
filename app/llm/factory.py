"""Runtime provider selection (the strategy chooser).

`LLM_PROVIDER` picks the backend; `auto` falls back through Anthropic -> OpenAI
-> Gemini -> Fake based on which API keys are present, so the app always starts
(keyless = Fake). Provider modules are imported lazily so an unselected
provider's SDK never needs to be installed.
"""
from __future__ import annotations

from ..config import Settings
from .base import LLMProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    choice = settings.llm_provider.lower()

    def anthropic() -> LLMProvider:
        if not settings.anthropic_api_key:
            raise RuntimeError("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set.")
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            settings.anthropic_api_key, settings.anthropic_model, settings.anthropic_thinking
        )

    def openai() -> LLMProvider:
        if not settings.openai_api_key:
            raise RuntimeError("LLM_PROVIDER=openai but OPENAI_API_KEY is not set.")
        from .openai_provider import OpenAIProvider

        return OpenAIProvider(settings.openai_api_key, settings.openai_model)

    def gemini() -> LLMProvider:
        key = settings.gemini_api_key or settings.google_api_key
        if not key:
            raise RuntimeError("LLM_PROVIDER=gemini but GEMINI_API_KEY/GOOGLE_API_KEY is not set.")
        from .gemini_provider import GeminiProvider

        return GeminiProvider(key, settings.gemini_model)

    def fake() -> LLMProvider:
        from .fake_provider import FakeProvider

        return FakeProvider()

    explicit = {"anthropic": anthropic, "openai": openai, "gemini": gemini, "fake": fake}
    if choice in explicit:
        return explicit[choice]()

    # auto: best available by key presence, never failing.
    if settings.anthropic_api_key:
        return anthropic()
    if settings.openai_api_key:
        return openai()
    if settings.gemini_api_key or settings.google_api_key:
        return gemini()
    return fake()
