"""Speech-to-text plug. Every provider returns the same shape, so we can swap vendors."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class Word:
    text: str
    start: float
    end: float
    speaker: int | None = None


@dataclass
class Segment:
    """Roughly one sentence. Clips are cut on segment edges so they start/end cleanly."""
    text: str
    start: float
    end: float


@dataclass
class SttResult:
    words: list[Word]
    segments: list[Segment]
    language: str | None = None
    audio_seconds: float = 0.0
    extra: dict = field(default_factory=dict)


class SpeechToText(Protocol):
    name: str
    #: longest audio piece the provider accepts in one request (we split longer audio)
    max_chunk_seconds: float

    def transcribe(self, audio: Path, language: str | None, prompt: str | None) -> SttResult:
        """Transcribe one audio file. Timestamps are relative to the start of that file."""
