"""Speech-to-text bake-off (Phase 2A).

  python -m clipverse_worker.evaluation draft   -> writes a draft answer key (samples/<name>.txt)
                                                   for every sample that doesn't have one yet
  python -m clipverse_worker.evaluation run     -> runs every candidate, scores it, writes eval/report.html

Samples: video or audio files in the main `samples/` folder. Only the first EVAL_SECONDS
(default 60 = 1 minute) of each file is used.
"""
from __future__ import annotations

import html
import json
import logging
import os
import sys
import time
from pathlib import Path

from .. import media
from ..config import REPO_ROOT, Settings
from ..errors import RetryLater
from ..pipeline.translit import to_roman
from . import scoring
from .candidates import make_candidates

SAMPLES = REPO_ROOT / "samples"
OUT = REPO_ROOT / "eval"
MEDIA_EXT = {".mp4", ".mov", ".mkv", ".webm", ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
DEFAULT_CANDIDATES = "groq:whisper-large-v3,groq:whisper-large-v3:auto,groq:whisper-large-v3-turbo,oriserve:Swift,srota"

log = logging.getLogger("eval")


def samples() -> list[Path]:
    return sorted(p for p in SAMPLES.iterdir() if p.suffix.lower() in MEDIA_EXT) if SAMPLES.exists() else []


def prepared_audio(src: Path) -> tuple[Path, Path]:
    """First N seconds as 16 kHz mono FLAC (for Groq) and WAV (for local models), cached."""
    seconds = int(os.getenv("EVAL_SECONDS", "60"))
    cache = OUT / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    flac, wav = cache / f"{src.stem}.{seconds}s.flac", cache / f"{src.stem}.{seconds}s.wav"
    for dest in (flac, wav):
        if not dest.exists():
            media.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-t", str(seconds), "-vn", "-ac", "1",
                       "-ar", "16000", str(dest)])
    return flac, wav


def draft(s: Settings) -> int:
    from ..pipeline.process import STT_PROMPT
    from ..providers.stt.groq import GroqStt
    files = samples()
    if not files:
        print(f"\nNo samples yet. Put a few short videos in: {SAMPLES}\n")
        return 1
    stt = GroqStt(s.groq_api_key, s.groq_stt_model)
    made = 0
    for f in files:
        key = f.with_suffix(".txt")
        if key.exists():
            print(f"  skip   {key.name} (already exists - your corrections are kept)")
            continue
        flac, _ = prepared_audio(f)
        res = stt.transcribe(flac, "hi", STT_PROMPT["hinglish"])
        lines = [to_roman(seg.text.strip()) for seg in res.segments] or [to_roman(" ".join(w.text for w in res.words))]
        key.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  made   {key.name}")
        made += 1
    secs = int(os.getenv("EVAL_SECONDS", "60"))
    print(f"\n{made} draft(s) written. Each covers the FIRST {secs} SECONDS of the video. Open each .txt in the "
          "samples folder and correct it so it matches EXACTLY what is said in that part - every word - in Roman "
          "Hinglish, with numbers as digits (90%, ₹200). Then run: npm run eval\n")
    return 0


def run(s: Settings) -> int:
    names = os.getenv("EVAL_CANDIDATES", DEFAULT_CANDIDATES).split(",")
    pairs = [(f, f.with_suffix(".txt")) for f in samples()]
    pairs = [(f, k) for f, k in pairs if k.exists()]
    if not pairs:
        print("\nNo samples with an answer key yet. Run 'npm run eval:draft' first, then correct the .txt files.\n")
        return 1
    fresh = "--fresh" in sys.argv
    results: dict[str, dict[str, dict]] = {}
    for cand in make_candidates(s, names):
        results[cand.name] = {}
        cdir = OUT / "results" / cand.name.replace(":", "_").replace("/", "_")
        cdir.mkdir(parents=True, exist_ok=True)
        for f, key in pairs:
            cache = cdir / f"{f.stem}.json"
            if cache.exists() and not fresh:
                results[cand.name][f.stem] = json.loads(cache.read_text(encoding="utf-8"))
                continue
            flac, wav = prepared_audio(f)
            print(f"  {cand.name:<34} {f.name} ...", flush=True)
            try:
                r = cand.run(flac if cand.name.startswith("groq") else wav, OUT / "cache")
            except RetryLater as e:
                print(f"     waiting {e.seconds:.0f}s ({e.reason})")
                time.sleep(min(e.seconds, 300))
                r = cand.run(flac if cand.name.startswith("groq") else wav, OUT / "cache")
            except ImportError as e:
                print(f"     skipped: needs the extra test packages (run 'npm run eval:setup'). {e}")
                break
            except Exception as e:  # noqa: BLE001 - keep testing the others
                print(f"     failed: {e}")
                continue
            entry = {"text": r.text, "seconds": r.seconds, "audio_seconds": media.probe_audio_duration(wav),
                     "usd_per_min": r.usd_per_min}
            cache.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
            results[cand.name][f.stem] = entry

    report = write_report(results, {f.stem: k.read_text(encoding="utf-8") for f, k in pairs})
    print(f"\nReport: {report}\n")
    return 0


def summarise(results: dict, refs: dict) -> list[dict]:
    rows = []
    for name, per in results.items():
        if not per:
            continue
        w = [scoring.wer(refs[k], v["text"]) for k, v in per.items()]
        c = [scoring.cer(refs[k], v["text"]) for k, v in per.items()]
        nums = [scoring.numbers_as_digits(refs[k], v["text"]) for k, v in per.items()]
        total_nums, hit = sum(n for n, _ in nums), sum(h for _, h in nums)
        audio = sum(v["audio_seconds"] for v in per.values())
        rows.append({
            "name": name, "samples": len(per),
            "wer": sum(w) / len(w), "cer": sum(c) / len(c),
            "digits": (hit / total_nums) if total_nums else None,
            "speed": sum(v["seconds"] for v in per.values()) / (audio / 60) if audio else 0,
            "usd_per_min": sum(v["usd_per_min"] for v in per.values()) / len(per),
            "devanagari": sum(scoring.script_mix(v["text"]) for v in per.values()) / len(per),
        })
    return sorted(rows, key=lambda r: r["wer"])


def write_report(results: dict, refs: dict) -> Path:
    rows = summarise(results, refs)
    pct = lambda x: "–" if x is None else f"{x * 100:.0f}%"
    e = html.escape
    summary = "".join(
        f"<tr{' class=win' if i == 0 else ''}><td>{e(r['name'])}{' <b>★ best</b>' if i == 0 else ''}</td>"
        f"<td>{pct(r['wer'])}</td><td>{pct(r['cer'])}</td><td>{pct(r['digits'])}</td>"
        f"<td>{r['speed']:.0f} s</td><td>${r['usd_per_min']:.4f} (₹{r['usd_per_min'] * 88:.2f})</td>"
        f"<td>{pct(r['devanagari'])}</td><td>{r['samples']}</td></tr>" for i, r in enumerate(rows))
    per_sample = ""
    warnings = []
    for stem, ref in refs.items():
        lengths = [len(scoring.normalize(per[stem]["text"])) for per in results.values() if stem in per]
        key_len = len(scoring.normalize(ref))
        if lengths and key_len and sorted(lengths)[len(lengths) // 2] > 1.6 * key_len:
            warnings.append(f"<li><b>{e(stem)}</b>: the answer key has {key_len} words, but the options heard about "
                            f"{sorted(lengths)[len(lengths) // 2]}. It's probably missing parts, so the scores for this "
                            "sample aren't reliable. Please complete it and run again with --fresh.</li>")
    warn_html = (f"<div class=warn><h2>⚠ Check these answer keys</h2><ul>{''.join(warnings)}</ul></div>"
                 if warnings else "")
    for stem, ref in refs.items():
        cells = "".join(
            f"<tr><td>{e(name)}</td><td>{pct(scoring.wer(ref, per[stem]['text']))}</td>"
            f"<td class=t>{e(per[stem]['text'][:600])}</td></tr>"
            for name, per in results.items() if stem in per)
        per_sample += (f"<h3>{e(stem)}</h3><p class=t><b>Answer key:</b> {e(ref[:600])}</p>"
                       f"<table><tr><th>Option</th><th>Word mistakes</th><th>What it wrote (start)</th></tr>{cells}</table>")
    page = f"""<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Speech-to-text test</title><style>
body{{background:#0B0B0D;color:#F5F5F7;font:15px/1.5 Inter,system-ui,sans-serif;margin:0;padding:24px 16px;max-width:1100px;margin:auto}}
h1,h2,h3{{letter-spacing:-.02em}} p,li{{color:#A1A1AA}} b{{color:#FF6B3D}}
table{{width:100%;border-collapse:collapse;margin:12px 0 28px;background:#111114;border-radius:16px;overflow:hidden;display:block;overflow-x:auto}}
th,td{{padding:10px 12px;border-bottom:1px solid #23232A;text-align:left;vertical-align:top}} th{{color:#A1A1AA;font-weight:500}}
tr.win td{{background:#1c1410}} .t{{font-size:13px;color:#d4d4d8}}
.warn{{border:1px solid #FF6B3D;border-radius:16px;padding:4px 20px;margin:16px 0;background:#1c1410}} .warn li{{color:#F5F5F7}}
</style><h1>Hinglish speech-to-text test</h1>
<p>Lower is better for mistakes. Everything is compared in Roman letters, so writing है or hai doesn't count as a mistake.</p>
{warn_html}<h2>Summary</h2><table><tr><th>Option</th><th>Word mistakes (WER)</th><th>Letter mistakes (CER)</th>
<th>Numbers as digits</th><th>Time per 1 min of audio</th><th>Cost per minute (paid plans)</th><th>Written in Devanagari</th><th>Samples</th></tr>{summary}</table>
<ul><li><b>Word mistakes</b>: of every 100 words in your answer key, how many were wrong, missing or extra.</li>
<li><b>Letter mistakes</b>: the same, counted letter by letter. Kinder to small spelling differences.</li>
<li><b>Time</b>: how long it took on this computer for 1 minute of audio.</li></ul>
<h2>Per sample</h2>{per_sample}</html>"""
    OUT.mkdir(exist_ok=True)
    path = OUT / "report.html"
    path.write_text(page, encoding="utf-8")
    return path


def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    s = Settings.load()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    return draft(s) if cmd == "draft" else run(s)


if __name__ == "__main__":
    sys.exit(main())
