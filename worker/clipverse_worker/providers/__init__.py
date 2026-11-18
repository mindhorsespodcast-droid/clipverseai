"""Pick the provider named in .env. Adding a vendor = one new file + one line here."""
from __future__ import annotations

from ..config import Settings
from ..errors import ConfigError


def make_stt(s: Settings):
    if s.stt_provider == "groq":
        from .stt.groq import GroqStt
        return GroqStt(s.groq_api_key, s.groq_stt_model)
    raise ConfigError(f"Unknown STT_PROVIDER '{s.stt_provider}'. Use: groq")


def make_llm(s: Settings, with_fallback: bool = True):
    from .llm.groq import FallbackLlm, GroqLlm
    if s.llm_provider == "gemini":
        from .llm.gemini import GeminiLlm
        main = GeminiLlm(s.gemini_api_key, s.gemini_model)
    elif s.llm_provider == "groq":
        main = GroqLlm(s.groq_api_key, s.groq_llm_model)
    else:
        raise ConfigError(f"Unknown LLM_PROVIDER '{s.llm_provider}'. Use: gemini or groq")
    if with_fallback and s.llm_fallback == "groq" and s.llm_provider != "groq" and s.groq_api_key:
        return FallbackLlm(main, GroqLlm(s.groq_api_key, s.groq_llm_model))
    return main


def make_storage(s: Settings):
    from .storage.local import LocalStorage
    return LocalStorage(s.storage_dir)
