"""All worker settings, read from the single .env file in the main clipverseai folder."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKER_DIR = REPO_ROOT / "worker"
FONTS_DIR = WORKER_DIR / "assets" / "fonts"
FACE_MODEL = WORKER_DIR / "assets" / "models" / "face_detection_yunet_2023mar.onnx"


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_secret_key: str
    storage_dir: Path
    stt_provider: str
    groq_api_key: str
    groq_stt_model: str
    llm_provider: str
    gemini_api_key: str
    gemini_model: str
    groq_llm_model: str
    llm_fallback: str
    clip_min_sec: int
    clip_max_sec: int
    max_clips: int
    max_video_hours: int
    usd_to_inr: float
    poll_seconds: float

    @staticmethod
    def load() -> "Settings":
        load_dotenv(REPO_ROOT / ".env")
        storage = os.getenv("STORAGE_DIR", "storage")
        storage_dir = Path(storage) if Path(storage).is_absolute() else REPO_ROOT / storage
        return Settings(
            supabase_url=os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").rstrip("/"),
            supabase_secret_key=os.getenv("SUPABASE_SECRET_KEY", ""),
            storage_dir=storage_dir,
            stt_provider=os.getenv("STT_PROVIDER", "groq").lower(),
            groq_api_key=os.getenv("GROQ_API_KEY", ""),
            groq_stt_model=os.getenv("GROQ_STT_MODEL", "whisper-large-v3"),
            llm_provider=os.getenv("LLM_PROVIDER", "gemini").lower(),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            groq_llm_model=os.getenv("GROQ_LLM_MODEL", "openai/gpt-oss-120b"),
            # backup AI when the main one hits its free-tier limit ("none" to switch off)
            llm_fallback=os.getenv("LLM_FALLBACK", "groq").lower(),
            clip_min_sec=_int("CLIP_MIN_SECONDS", 15),
            clip_max_sec=_int("CLIP_MAX_SECONDS", 90),
            max_clips=_int("MAX_CLIPS_PER_VIDEO", 10),
            max_video_hours=_int("MAX_VIDEO_HOURS", 6),
            usd_to_inr=float(os.getenv("USD_TO_INR", "88")),
            poll_seconds=float(os.getenv("WORKER_POLL_SECONDS", "3")),
        )

    def problems(self) -> list[str]:
        """Plain-English list of missing settings (empty list = all good)."""
        out = []
        if not self.supabase_url or "your-project-id" in self.supabase_url:
            out.append("NEXT_PUBLIC_SUPABASE_URL is missing (README, Phase 0 step 3).")
        if not self.supabase_secret_key.startswith("sb_secret_"):
            out.append("SUPABASE_SECRET_KEY is missing. Copy the SECRET key (sb_secret_...) from "
                       "Supabase > Project Settings > API Keys.")
        if self.stt_provider == "groq" and not self.groq_api_key:
            out.append("GROQ_API_KEY is missing. Get a free key at console.groq.com > API Keys.")
        if self.llm_provider == "groq" and not self.groq_api_key:
            out.append("GROQ_API_KEY is missing. Get a free key at console.groq.com > API Keys.")
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            out.append("GEMINI_API_KEY is missing. Get a free key at aistudio.google.com > Get API key.")
        return out
