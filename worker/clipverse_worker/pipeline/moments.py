"""Clip finder: ask the LLM for the best moments, then clean up its answer.

The transcript is sent as numbered sentences ("segments"). The LLM answers with
segment numbers, so every clip naturally starts and ends on a full sentence.
Long videos are split into overlapping windows; results are merged and de-duplicated.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..providers.llm.base import LlmUsage
from .profiles import PROFILES

WINDOW_SEC = 12 * 60
OVERLAP_SEC = 2 * 60

SYSTEM = (
    "You are a senior short-form video editor for Indian creators. You know what Indian audiences "
    "share on Instagram Reels and YouTube Shorts: Hinglish banter, desi humour, relatable middle-class "
    "moments, cricket/Bollywood references, money and career talk, bold opinions. You pick moments "
    "that work on their own, without the rest of the video. Always answer with JSON only."
)


@dataclass
class Moment:
    start: float
    end: float
    score: int
    title: str
    reason: str

    @property
    def duration(self) -> float:
        return self.end - self.start


def fmt_time(t: float) -> str:
    m, s = divmod(int(t), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def windows(segments: list[dict]) -> list[list[int]]:
    """Indexes of segments in each ~12-minute window (2-minute overlap)."""
    if not segments:
        return []
    total = segments[-1]["end"]
    out, start = [], 0.0
    while True:
        end = start + WINDOW_SEC
        idx = [i for i, s in enumerate(segments) if s["end"] > start and s["start"] < end]
        if idx:
            out.append(idx)
        if end >= total:
            return out
        start = end - OVERLAP_SEC


def build_prompt(segments: list[dict], idx: list[int], content_type: str, want: int,
                 min_sec: int, max_sec: int, topic: str | None = None) -> str:
    lines = "\n".join(f"S{i} [{fmt_time(segments[i]['start'])}-{fmt_time(segments[i]['end'])}] "
                      f"{segments[i]['text']}" for i in idx)
    focus = f'\nOnly pick moments about: "{topic}".' if topic else ""
    return f"""Video type: {PROFILES.get(content_type, PROFILES['other'])}{focus}

Below is part of the transcript, one numbered sentence per line (S<number> [start-end] text).
The speech may be Hindi, English or Hinglish, in Devanagari or Roman script.

{lines}

Pick up to {want} of the best standalone short clips from this part.
Rules:
- Each clip is a continuous range of sentences, from start_segment to end_segment (inclusive).
- Length between {min_sec} and {max_sec} seconds; 30-60 seconds is ideal.
- The first sentence must hook the viewer immediately. The last sentence must finish the thought.
- Don't pick overlapping clips. Skip intros, sponsor reads, and "like and subscribe" parts.
- score: 0-100, how likely it is to do well on Reels/Shorts. Be strict: 90+ is rare.
- title: a punchy hook title in the same language style as the speaker (Hinglish in Roman script if they speak Hinglish), max 60 characters.
- reason: one short line (max 100 characters) on why it works.
- If nothing here is worth posting, return an empty list.

Answer as JSON: {{"clips": [{{"start_segment": 12, "end_segment": 19, "score": 82, "title": "...", "reason": "..."}}]}}"""


def _fit_length(segments: list[dict], a: int, b: int, min_sec: float, max_sec: float) -> tuple[int, int] | None:
    """Grow/shrink a sentence range so it fits the allowed length, keeping sentence edges."""
    dur = lambda: segments[b]["end"] - segments[a]["start"]
    while dur() > max_sec and b > a:
        b -= 1
    while dur() < min_sec and b + 1 < len(segments) and \
            segments[b + 1]["end"] - segments[a]["start"] <= max_sec:
        b += 1
    while dur() < min_sec and a > 0 and segments[b]["end"] - segments[a - 1]["start"] <= max_sec:
        a -= 1
    return (a, b) if min_sec <= dur() <= max_sec else None


def parse_moments(answer, segments: list[dict], allowed: set[int], min_sec: float,
                  max_sec: float) -> list[Moment]:
    out = []
    items = answer.get("clips", []) if isinstance(answer, dict) else answer if isinstance(answer, list) else []
    for c in items:
        try:
            a, b = int(str(c["start_segment"]).lstrip("S")), int(str(c["end_segment"]).lstrip("S"))
        except (KeyError, TypeError, ValueError):
            continue
        if a not in allowed or b not in allowed or b < a:
            continue
        fitted = _fit_length(segments, a, b, min_sec, max_sec)
        if not fitted:
            # one very long sentence: keep it but cut at max length
            if segments[b]["end"] - segments[a]["start"] > max_sec:
                start = segments[a]["start"]
                fitted_m = (start, start + max_sec)
            else:
                continue
        else:
            fitted_m = (segments[fitted[0]]["start"], segments[fitted[1]]["end"])
        try:
            score = max(0, min(100, int(round(float(c.get("score", 50) or 50)))))
        except (TypeError, ValueError):
            score = 50
        out.append(Moment(start=round(fitted_m[0], 3), end=round(fitted_m[1], 3), score=score,
                          title=str(c.get("title") or "Untitled clip").strip()[:80],
                          reason=str(c.get("reason") or "").strip()[:160]))
    return out


def overlap_ratio(a: Moment, b: Moment) -> float:
    inter = max(0.0, min(a.end, b.end) - max(a.start, b.start))
    return inter / min(a.duration, b.duration)


def dedupe(moments: list[Moment], max_overlap: float = 0.4) -> list[Moment]:
    kept: list[Moment] = []
    for m in sorted(moments, key=lambda m: -m.score):
        if all(overlap_ratio(m, k) <= max_overlap for k in kept):
            kept.append(m)
    return kept


def target_count(duration_sec: float, cap: int) -> int:
    """About 20 clips per hour (brief: 10-30), at least 3, at most `cap`."""
    return max(3, min(cap, math.ceil(duration_sec / 3600 * 20)))


def find_moments(llm, segments: list[dict], content_type: str, duration: float, min_sec: int,
                 max_sec: int, cap: int, topic: str | None = None) -> tuple[list[Moment], LlmUsage]:
    usage = LlmUsage()
    found: list[Moment] = []
    for idx in windows(segments):
        span = segments[idx[-1]]["end"] - segments[idx[0]]["start"]
        want = max(2, min(8, math.ceil(span / 60 / 2)))  # ~1 candidate per 2 minutes
        answer, u = llm.complete_json(
            "moments", SYSTEM, build_prompt(segments, idx, content_type, want, min_sec, max_sec, topic))
        usage.add(u)
        found += parse_moments(answer, segments, set(idx), min_sec, max_sec)
    best = dedupe(found)[: target_count(duration, cap)]
    return sorted(best, key=lambda m: -m.score), usage
