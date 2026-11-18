"""Groq's hosted Whisper (free tier with daily limits). Docs: console.groq.com/docs/speech-to-text"""
from __future__ import annotations

from pathlib import Path

import httpx

from ...errors import RetryLater, UserFacingError
from .base import Segment, SttResult, Word

URL = "https://api.groq.com/openai/v1/audio/transcriptions"


class GroqStt:
    name = "groq"
    # ~10 minutes of 16kHz mono FLAC is ~10 MB, safely under the free tier's 25 MB upload limit.
    max_chunk_seconds = 600.0

    def __init__(self, api_key: str, model: str, client: httpx.Client | None = None):
        self.api_key = api_key
        self.model = model
        self._http = client or httpx.Client(timeout=300)

    def transcribe(self, audio: Path, language: str | None, prompt: str | None) -> SttResult:
        # httpx needs a dict here; a list value sends the field once per item.
        data: dict[str, str | list[str]] = {
            "model": self.model,
            "response_format": "verbose_json",
            "timestamp_granularities[]": ["word", "segment"],
            "temperature": "0",
        }
        if language:
            data["language"] = language
        if prompt:
            data["prompt"] = prompt[:800]

        with audio.open("rb") as fh:
            try:
                res = self._http.post(
                    URL,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data=data,
                    files={"file": (audio.name, fh, "audio/flac")},
                )
            except httpx.HTTPError as e:
                raise RetryLater(60, f"Couldn't reach Groq ({e.__class__.__name__})") from e

        if res.status_code == 429:
            wait = float(res.headers.get("retry-after", "60") or 60)
            raise RetryLater(wait, "Groq free-tier limit reached; waiting before trying again")
        if res.status_code in (401, 403):
            raise UserFacingError("The Groq API key was rejected. Check GROQ_API_KEY in .env.")
        if res.status_code >= 500:
            raise RetryLater(60, f"Groq is having trouble (error {res.status_code})")
        if res.status_code >= 400:
            raise RuntimeError(f"Groq error {res.status_code}: {res.text[:300]}")

        body = res.json()
        words = [
            Word(text=str(w.get("word", "")).strip(), start=float(w["start"]), end=float(w["end"]))
            for w in body.get("words") or []
            if str(w.get("word", "")).strip()
        ]
        segments = [
            Segment(text=str(s.get("text", "")).strip(), start=float(s["start"]), end=float(s["end"]))
            for s in body.get("segments") or []
            if str(s.get("text", "")).strip()
        ]
        return SttResult(
            words=words,
            segments=segments,
            language=body.get("language"),
            audio_seconds=float(body.get("duration") or 0),
        )
