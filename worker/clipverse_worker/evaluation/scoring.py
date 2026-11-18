"""How we score a transcript against the corrected "answer key".

Hinglish is spelled many ways (है / hai / he, नहीं / nahi / nahin), so before comparing we:
  1. convert any Devanagari to Roman letters (our built-in converter),
  2. lowercase, drop punctuation,
  3. even out common spelling variants (aa->a, ee->i, oo->u, w->v, z->j, final "n" nasal).
Then we count word mistakes (WER) and letter mistakes (CER, more forgiving of spelling).
"""
from __future__ import annotations

import re

from ..pipeline.translit import to_roman

_NUM = re.compile(r"[₹$]?\d[\d,.]*%?")


def normalize(text: str) -> list[str]:
    t = to_roman(text).lower()
    t = t.replace("₹", " rs ").replace("%", " percent ")
    t = re.sub(r"[^\w\s]", " ", t)
    words = []
    for w in t.split():
        if not w.isdigit():
            w = w.replace("ee", "i").replace("oo", "u").replace("w", "v").replace("z", "j")
            w = re.sub(r"(.)\1+", r"\1", w)          # double letters: "baat" -> "bat", "accha" -> "acha"
            w = re.sub(r"(?<=[aeiou])n$", "", w)    # hain/hai, mein/mei, nahin/nahi
            w = re.sub(r"(?<=[kgcjtdpb])h", "", w)  # aspirates spelled loosely: bhi/bi, kuch/kuc
        words.append(w)
    return words


def _edits(a: list, b: list) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def wer(reference: str, hypothesis: str) -> float:
    r, h = normalize(reference), normalize(hypothesis)
    return _edits(r, h) / max(1, len(r))


def cer(reference: str, hypothesis: str) -> float:
    r, h = " ".join(normalize(reference)), " ".join(normalize(hypothesis))
    return _edits(list(r), list(h)) / max(1, len(r))


def numbers_as_digits(reference: str, hypothesis: str) -> tuple[int, int]:
    """(numbers in the answer key, how many of them the transcript wrote as digits)."""
    ref_nums = [re.sub(r"[^\d]", "", n) for n in _NUM.findall(reference)]
    hyp_digits = re.sub(r"[^\d ]", "", " ".join(_NUM.findall(hypothesis))).split()
    hits = 0
    pool = list(hyp_digits)
    for n in ref_nums:
        if n in pool:
            pool.remove(n)
            hits += 1
    return len(ref_nums), hits


def script_mix(text: str) -> float:
    """Share of words in Devanagari (0..1) - shows how each model writes Hinglish."""
    words = [w for w in text.split() if re.search(r"\w", w)]
    return sum(1 for w in words if re.search(r"[ऀ-ॿ]", w)) / len(words) if words else 0.0
