"""Builds the ASS subtitle file that FFmpeg burns into the clip.

Style "Bold pop" (Phase 1's one style): big bold white words with a thick black
outline (readable on any background), 1-3 words on screen at a time, the word
being spoken pops slightly bigger, and highlighted keywords are in our accent orange.
"""
from __future__ import annotations

ACCENT = "&H003D6BFF"  # #FF6B3D in ASS's blue-green-red order
WHITE = "&H00FFFFFF"

FONTS = {"roman": ("Noto Sans", 104), "devanagari": ("Noto Sans Devanagari", 112)}


def _ts(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")


def group_phrases(words: list[dict], script: str, max_words: int = 3, max_chars: int = 16,
                  max_gap: float = 0.6) -> list[list[dict]]:
    """Split words into short on-screen phrases. A pause or sentence end starts a new phrase."""
    phrases, cur = [], []
    for w in words:
        text = w.get(script)
        if text is None:  # no converted version: use the original word
            text = w.get("text") or ""
        if not text:  # deliberately blank, e.g. "सौ" after "दो सौ" became "200"
            continue
        w = w | {"_t": text}
        too_long = cur and (len(cur) >= max_words or sum(len(x["_t"]) + 1 for x in cur) + len(text) > max_chars)
        gap = cur and w["start"] - cur[-1]["end"] > max_gap
        if too_long or gap:
            phrases.append(cur)
            cur = []
        cur.append(w)
        if text[-1] in ".?!।":
            phrases.append(cur)
            cur = []
    if cur:
        phrases.append(cur)
    return phrases


def build_ass(words: list[dict], script: str, clip_duration: float) -> str:
    """`words` have times relative to the clip start."""
    font, size = FONTS[script]
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pop,{font},{size},{WHITE},{WHITE},&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,7,0,2,70,70,560,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for phrase in group_phrases(words, script):
        for i, w in enumerate(phrase):
            start = w["start"]
            # stay on screen until the next word (or a little after the last one)
            end = phrase[i + 1]["start"] if i + 1 < len(phrase) else min(w["end"] + 0.3, clip_duration)
            if end <= start:
                end = start + 0.05
            parts = []
            for j, x in enumerate(phrase):
                colour = ACCENT if x.get("hl") else WHITE
                text = _escape(x["_t"])
                if j == i:
                    parts.append(f"{{\\c{colour}\\fscx112\\fscy112}}{text}{{\\fscx100\\fscy100}}")
                else:
                    parts.append(f"{{\\c{colour}}}{text}")
            lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Pop,,0,0,0,,{' '.join(parts)}")
    return header + "\n".join(lines) + "\n"
