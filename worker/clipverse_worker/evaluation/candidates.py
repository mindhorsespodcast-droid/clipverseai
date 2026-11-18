"""The speech-to-text options we compare. Each returns plain text for one audio file.

Groq ones use the internet (free tier). The others download a model once (from Hugging Face)
and run on this computer - free, but slow without a graphics card.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from .. import media, pricing
from ..config import Settings


@dataclass
class Result:
    text: str
    seconds: float          # time taken
    usd_per_min: float      # estimated cost per audio minute (0 for local models)


class GroqCandidate:
    def __init__(self, s: Settings, model: str):
        from ..pipeline.process import STT_PROMPT
        from ..providers.stt.groq import GroqStt
        self.name = f"groq:{model}"
        self.stt = GroqStt(s.groq_api_key, model)
        self.prompt = STT_PROMPT["hinglish"]
        self.model = model

    def run(self, audio: Path, work: Path) -> Result:
        t = time.monotonic()
        res = self.stt.transcribe(audio, "hi", self.prompt)
        text = " ".join(seg.text for seg in res.segments) or " ".join(w.text for w in res.words)
        return Result(text, time.monotonic() - t, pricing.stt_cost(self.model, 60))


class OriserveCandidate:
    """Oriserve Whisper-Hindi2Hinglish: writes Hinglish in Roman letters. Apache-2.0."""

    def __init__(self, model_id: str = "Oriserve/Whisper-Hindi2Hinglish-Swift"):
        self.name = model_id.split("/")[-1]
        self.model_id = model_id
        self._pipe = None

    def _load(self):
        if self._pipe is None:
            import torch
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
            torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))
            model = AutoModelForSpeechSeq2Seq.from_pretrained(self.model_id, torch_dtype=torch.float32,
                                                              low_cpu_mem_usage=True, use_safetensors=True)
            proc = AutoProcessor.from_pretrained(self.model_id)
            self._pipe = pipeline("automatic-speech-recognition", model=model, tokenizer=proc.tokenizer,
                                  feature_extractor=proc.feature_extractor, device="cpu", chunk_length_s=30,
                                  generate_kwargs={"task": "transcribe", "language": "en"})
        return self._pipe

    def run(self, audio: Path, work: Path) -> Result:
        pipe = self._load()
        t = time.monotonic()
        out = pipe(str(audio), return_timestamps=True)
        return Result(out["text"].strip(), time.monotonic() - t, 0.0)


def utterances(audio: Path, max_len: float = 20.0, pad: float = 0.15) -> list[tuple[float, float]]:
    """Speech-only pieces, one per sentence: from the end of one pause to the start of the next.
    Models trained on single sentences stop after the first pause in a longer piece, and
    invent text when handed silence - so we give them neither."""
    duration = media.probe_audio_duration(audio)
    silences = media.find_silences(audio, min_silence=0.3)
    edges = [0.0] + [x for pair in silences for x in pair] + [duration]
    pieces = []
    for a, b in zip(edges[0::2], edges[1::2]):   # (end of pause, start of next pause) = speech
        a, b = max(0.0, a - pad), min(duration, b + pad)
        while b - a > max_len:
            pieces.append((a, a + max_len))
            a += max_len
        if b - a >= 0.3:
            pieces.append((a, b))
    return pieces


class SrotaCandidate:
    """Srota (Qwen3-ASR Hinglish): Hindi in Devanagari, English in Latin. Apache-2.0.
    Trained on single sentences of <= 30 s, so we give it one sentence (pause to pause) at a time."""

    name = "srota-qwen3-asr-hinglish"

    def __init__(self, model_id: str = "moorlee/qwen3-asr-0.6b-hinglish"):
        self.model_id = model_id
        self._model = None

    def _load(self):
        if self._model is None:
            import torch
            from qwen_asr import Qwen3ASRModel
            torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))
            self._model = Qwen3ASRModel.from_pretrained(self.model_id, dtype=torch.float32, device_map="cpu")
        return self._model

    def run(self, audio: Path, work: Path) -> Result:
        model = self._load()
        pieces = utterances(audio)
        t = time.monotonic()
        texts = []
        for k, (a, b) in enumerate(pieces):
            piece = work / f"srota_{k}.wav"
            media.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(audio),
                       "-ac", "1", "-ar", "16000", str(piece)])
            texts.append(model.transcribe(audio=str(piece), language=None)[0].text.strip())
            piece.unlink(missing_ok=True)
        return Result(" ".join(texts), time.monotonic() - t, 0.0)


def make_candidates(s: Settings, names: list[str]):
    out = []
    for n in names:
        n = n.strip()
        if n.startswith("groq:"):
            out.append(GroqCandidate(s, n.split(":", 1)[1]))
        elif n.startswith("oriserve"):
            out.append(OriserveCandidate("Oriserve/Whisper-Hindi2Hinglish-" + (n.split(":", 1)[1] if ":" in n else "Swift")))
        elif n == "srota":
            out.append(SrotaCandidate())
    return out
