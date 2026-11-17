"""Stand-ins for the database, speech-to-text and LLM so the pipeline can be tested offline."""
from __future__ import annotations

import copy
import re
import subprocess
import uuid
from pathlib import Path

from clipverse_worker.providers.llm.base import LlmUsage
from clipverse_worker.providers.stt.base import Segment, SttResult, Word

DEFAULTS = {
    "clips": {"status": "pending", "outputs": {}, "words": None, "crop_track": None, "layout": "auto", "error": None},
    "jobs": {"status": "queued", "attempts": 0, "max_attempts": 3, "payload": {}, "cost_breakdown": {},
             "run_after": "1970-01-01T00:00:00+00:00"},
}


class FakeDb:
    def __init__(self):
        self.tables: dict[str, list[dict]] = {}

    def _rows(self, table):
        return self.tables.setdefault(table, [])

    @staticmethod
    def _match(row, where):
        return all(str(row.get(k)) == str(v) for k, v in where.items())

    def select(self, table, where, columns="*", order=None):
        rows = [copy.deepcopy(r) for r in self._rows(table) if self._match(r, where)]
        if order:
            col, _, direction = order.partition(".")
            rows.sort(key=lambda r: r.get(col) or 0, reverse=direction == "desc")
        return rows

    def select_one(self, table, where):
        rows = self.select(table, where)
        return rows[0] if rows else None

    def insert(self, table, rows):
        rows = rows if isinstance(rows, list) else [rows]
        out = []
        for r in rows:
            r = copy.deepcopy(DEFAULTS.get(table, {})) | {"id": str(uuid.uuid4())} | copy.deepcopy(r)
            self._rows(table).append(r)
            out.append(copy.deepcopy(r))
        return out

    def update(self, table, where, values):
        out = []
        for r in self._rows(table):
            if self._match(r, where):
                r.update(copy.deepcopy(values))
                out.append(copy.deepcopy(r))
        return out

    def delete(self, table, where):
        self.tables[table] = [r for r in self._rows(table) if not self._match(r, where)]

    def rpc(self, fn, args=None):
        if fn == "requeue_stale_jobs":
            return 0
        if fn == "claim_job":
            for r in self._rows("jobs"):
                if r["status"] == "queued" and r["run_after"] <= "1970-01-02":
                    r.update(status="running", attempts=r["attempts"] + 1)
                    return [copy.deepcopy(r)]
            return []
        raise KeyError(fn)


SENTENCES = [
    "दोस्तों आज हम बात करेंगे creator economy के बारे में",
    "नब्बे प्रतिशत creators यह गलती करते हैं",
    "algorithm सब कुछ नहीं है consistency ज़रूरी है",
    "brand deals का असली rate क्या है यह मैं बताता हूं",
    "पहले साल मैंने सिर्फ दो सौ रुपये कमाए थे",
    "Hindi content का future बहुत bright है",
]


class FakeStt:
    name = "fake"
    model = "whisper-large-v3"
    max_chunk_seconds = 60.0

    def transcribe(self, audio: Path, language, prompt):
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                              str(audio)], capture_output=True, text=True)
        duration = float(out.stdout.strip())
        words, segments, t, k = [], [], 0.3, 0
        while t < duration - 3:
            sentence = SENTENCES[k % len(SENTENCES)].split()
            seg_start = t
            for w in sentence:
                words.append(Word(w, round(t, 2), round(t + 0.35, 2)))
                t += 0.45
            segments.append(Segment(" ".join(sentence) + "।", seg_start, t - 0.1))
            t += 0.6
            k += 1
        return SttResult(words=words, segments=segments, language="hi", audio_seconds=duration)


ROMAN = {"दोस्तों": "Dosto", "आज": "aaj", "हम": "hum", "बात": "baat", "करेंगे": "karenge", "के": "ke",
         "बारे": "baare", "में": "mein", "यह": "yeh", "गलती": "galti", "करते": "karte", "हैं": "hain",
         "सब": "sab", "कुछ": "kuch", "नहीं": "nahi", "है": "hai", "ज़रूरी": "zaroori", "का": "ka",
         "असली": "asli", "क्या": "kya", "मैं": "main", "बताता": "batata", "हूं": "hoon", "पहले": "pehle",
         "साल": "saal", "मैंने": "maine", "सिर्फ": "sirf", "कमाए": "kamaye", "थे": "the", "बहुत": "bahut"}
DEVA = {"creator": "क्रिएटर", "economy": "इकॉनमी", "creators": "क्रिएटर्स", "algorithm": "एल्गोरिदम",
        "consistency": "कंसिस्टेंसी", "brand": "ब्रांड", "deals": "डील्स", "rate": "रेट", "Hindi": "हिंदी",
        "content": "कंटेंट", "future": "फ्यूचर", "bright": "ब्राइट"}


class FakeLlm:
    name = "fake"
    model = "gemini-2.5-flash"

    def __init__(self, fail_scripts: bool = False):
        self.calls = []
        self.fail_scripts = fail_scripts

    def complete_json(self, task, system, prompt):
        self.calls.append(task)
        usage = LlmUsage(input_tokens=len(prompt) // 4, output_tokens=200)
        if task == "moments":
            ids = [int(x) for x in re.findall(r"^S(\d+) \[", prompt, re.M)]
            clips = []
            for n, a in enumerate(range(ids[0], ids[-1] - 6, 9)):
                clips.append({"start_segment": a, "end_segment": a + 6, "score": 90 - n * 7,
                              "title": f"Clip {n + 1}: creators yeh galti karte hain", "reason": "Strong hook"})
            return {"clips": clips[:3]}, usage
        if task == "scripts":
            if self.fail_scripts:
                return {"roman": [], "devanagari": []}, usage
            tokens = [line.split(": ", 1)[1] for line in re.findall(r"^\d+: .+$", prompt, re.M)]
            roman, deva, hl = [], [], []
            skip = False
            for i, t in enumerate(tokens):
                if skip:
                    roman.append(""); deva.append(""); skip = False
                    continue
                if t == "नब्बे":
                    roman.append("90%"); deva.append("90%"); hl.append(i); skip = True
                    continue
                if t == "दो":
                    roman.append("₹200"); deva.append("₹200"); hl.append(i)
                    continue
                if t in ("सौ", "रुपये"):
                    roman.append(""); deva.append("")
                    continue
                roman.append(ROMAN.get(t, t)); deva.append(DEVA.get(t, t))
            return {"roman": roman, "devanagari": deva, "highlight": hl}, usage
        raise KeyError(task)
