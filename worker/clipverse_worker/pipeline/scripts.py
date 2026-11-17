"""Caption scripts: turn a clip's spoken words into Roman Hinglish AND Devanagari.

Whisper writes Hindi in Devanagari or Roman unpredictably, and spells numbers out.
We send the clip's words to the LLM in small batches and ask for both scripts,
word-for-word, with numbers as digits and keywords marked for highlighting.
If the LLM fails or returns the wrong number of words, we keep the original
words so a clip is never lost because of this step.
"""
from __future__ import annotations

import re

from ..providers.llm.base import LlmUsage

BATCH = 120  # words per request

SYSTEM = ("You convert Hindi/Hinglish/English speech transcripts into clean caption text for Indian "
          "short-form videos. Always answer with JSON only.")

DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def build_prompt(tokens: list[str]) -> str:
    numbered = "\n".join(f"{i}: {t}" for i, t in enumerate(tokens))
    return f"""Here are {len(tokens)} spoken words from a video, one per line ("index: word").

{numbered}

For EACH index return:
- roman: the word in natural Roman Hinglish, the way Indian creators type (yeh, nahi, hai, kya, matlab). English words keep normal English spelling.
- devanagari: the word in Devanagari. English words are written phonetically in Devanagari (creators -> क्रिएटर्स).
Rules:
- Return EXACTLY {len(tokens)} items in each list, in the same order. Never merge or split items, except:
- Numbers: write them as digits in BOTH scripts ("नब्बे प्रतिशत" -> "90%", "two hundred rupees" -> "₹200"). If a number spans several words, put the full number in the first word's slot and "" in the other slots.
- Keep punctuation attached to its word. Do not translate, fix grammar, or censor.
- highlight: indexes of up to 1 in 6 words worth highlighting (numbers, names, brands, the key word of a punchline).

Answer as JSON: {{"roman": ["..."], "devanagari": ["..."], "highlight": [3, 9]}}"""


def _fallback(words: list[dict]) -> list[dict]:
    return [w | {"roman": w["text"], "devanagari": w["text"], "hl": bool(re.search(r"\d", w["text"]))}
            for w in words]


def convert_words(llm, words: list[dict]) -> tuple[list[dict], LlmUsage, bool]:
    """words: [{"start", "end", "text"}] -> same list with "roman", "devanagari", "hl".
    Returns (words, usage, all_batches_ok)."""
    usage, out, ok = LlmUsage(), [], True
    for i in range(0, len(words), BATCH):
        batch = words[i:i + BATCH]
        tokens = [w["text"] for w in batch]
        try:
            answer, u = llm.complete_json("scripts", SYSTEM, build_prompt(tokens))
            usage.add(u)
            roman, deva = answer.get("roman", []), answer.get("devanagari", [])
            hl = {int(x) for x in answer.get("highlight", []) if str(x).lstrip("-").isdigit()}
            if len(roman) != len(tokens) or len(deva) != len(tokens):
                raise ValueError("word count mismatch")
            out += [w | {"roman": str(r).strip(), "devanagari": str(d).strip(), "hl": j in hl}
                    for j, (w, r, d) in enumerate(zip(batch, roman, deva))]
        except Exception:  # noqa: BLE001 - never lose a clip over captions
            ok = False
            out += _fallback(batch)
    return out, usage, ok
