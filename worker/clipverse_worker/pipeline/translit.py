"""Rule-based Devanagari -> Roman Hinglish, used only as a BACKUP when the AI's caption
conversion fails. Not perfect, but readable the way creators type (जिनमें -> jinmen).
Pure Python, no extra packages."""
from __future__ import annotations

import re

VOWELS = {"अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ऋ": "ri", "ए": "e", "ऐ": "ai",
          "ओ": "o", "औ": "au", "ऑ": "o", "ऍ": "e"}
MATRAS = {"ा": "a", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "ृ": "ri", "े": "e", "ै": "ai", "ो": "o",
          "ौ": "au", "ॉ": "o", "ॅ": "e"}
CONSONANTS = {"क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh",
              "ञ": "n", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d",
              "ध": "dh", "न": "n", "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r",
              "ल": "l", "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h", "ळ": "l",
              "क़": "q", "ख़": "kh", "ग़": "gh", "ज़": "z", "ड़": "d", "ढ़": "dh", "फ़": "f", "य़": "y"}
NUKTA, VIRAMA, ANUSVARA, CHANDRABINDU, VISARGA = "़", "्", "ं", "ँ", "ः"
DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
WORDS = {"है": "hai", "हैं": "hain", "में": "mein", "मैं": "main", "नहीं": "nahi", "यह": "yeh", "वह": "woh",
         "और": "aur", "क्या": "kya", "क्यों": "kyun", "तो": "toh", "हम": "hum", "हां": "haan", "हाँ": "haan"}


def _word(w: str) -> str:
    if w in WORDS:
        return WORDS[w]
    # Build units: [consonant letters, vowel letters, vowel_is_the_hidden_a]
    units: list[list] = []
    chars = list(w)
    i = 0
    while i < len(chars):
        c = chars[i]
        if i + 1 < len(chars) and chars[i + 1] == NUKTA and c + NUKTA in CONSONANTS:
            c = c + NUKTA
            i += 1
        nxt = chars[i + 1] if i + 1 < len(chars) else ""
        if c in CONSONANTS:
            if nxt in MATRAS:
                units.append([CONSONANTS[c], MATRAS[nxt], False])
                i += 1
            elif nxt == VIRAMA:
                units.append([CONSONANTS[c], "", False])
                i += 1
            else:
                units.append([CONSONANTS[c], "a", True])
        elif c in VOWELS:
            units.append(["", VOWELS[c], False])
        elif c in (ANUSVARA, CHANDRABINDU) and units:
            units[-1][1] += "n"
        elif c == VISARGA and units:
            units[-1][1] += "h"
        elif c in ("।", "॥"):
            units.append([".", "", False])
        else:
            units.append([c.translate(DIGITS), "", False])
        i += 1

    letters = [u for u in units if u[0] not in (".",) and (u[0] or u[1])]
    # Hindi drops the hidden "a" at the end of a word (kamal, not kamala) ...
    if len(letters) > 1 and letters[-1][2]:
        letters[-1][1] = ""
    # ... and between consonants when both neighbours have a vowel (jin-men, kar-te).
    k = len(letters) - 2
    while k >= 1:
        prev, cur, nxt = letters[k - 1], letters[k], letters[k + 1]
        # (not after a closed syllable like "zin-" in zindagi)
        if cur[2] and cur[1] == "a" and prev[1] and not prev[1].endswith(("n", "h")) and nxt[1] and nxt[0]:
            cur[1] = ""
            k -= 2
        else:
            k -= 1
    # word-final ी is typed "i" (galti, zindagi, nahi)
    if letters and letters[-1][1] == "ee":
        letters[-1][1] = "i"
    return "".join(u[0] + u[1] for u in units)


def to_roman(text: str) -> str:
    """Transliterate any Devanagari words inside `text`; leave everything else as it is."""
    return re.sub(r"[ऀ-ॿ]+", lambda m: _word(m.group(0)), text)
