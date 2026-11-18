"""List prices used to ESTIMATE what each job would cost on paid plans.

We're on free tiers in Phase 1, so the real bill is ₹0 - but we log the
estimate anyway so we know our true cost per minute of video before launch.
Update these numbers from the providers' pricing pages when they change.
"""

# Groq Whisper: USD per hour of audio (groq.com/pricing; billed per request, min 10 s)
STT_USD_PER_HOUR = {
    "whisper-large-v3": 0.111,
    "whisper-large-v3-turbo": 0.04,
}

# LLMs: USD per 1 million tokens (input, output)
LLM_USD_PER_MILLION = {
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    # Groq (groq.com/pricing)
    "openai/gpt-oss-120b": (0.15, 0.75),
    "openai/gpt-oss-20b": (0.075, 0.30),
    "llama-3.3-70b-versatile": (0.59, 0.79),
}
# Models not listed (e.g. newer Gemini versions) use DEFAULT_LLM: an estimate until we add real prices.
DEFAULT_LLM = (0.30, 2.50)


def stt_cost(model: str, audio_seconds: float) -> float:
    rate = STT_USD_PER_HOUR.get(model, 0.111)
    return rate * max(audio_seconds, 10.0) / 3600.0


def llm_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    inp, out = LLM_USD_PER_MILLION.get(model, DEFAULT_LLM)
    return (input_tokens * inp + output_tokens * out) / 1_000_000
