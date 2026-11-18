"""Start the worker:   python -m clipverse_worker          (keeps running)
Check settings:       python -m clipverse_worker check
"""
from __future__ import annotations

import logging
import sys

import httpx

from .config import Settings
from .db import Db, DbError
from .errors import ConfigError
from .media import require_ffmpeg
from .errors import UserFacingError
from .pipeline.process import Ctx
from .providers import make_llm, make_storage, make_stt
from .worker import loop


def _setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)


def check(s: Settings) -> int:
    """Plain-English health check of everything the worker needs."""
    ok = True

    def line(good: bool, msg: str) -> None:
        nonlocal ok
        ok = ok and good
        print(f"  {'OK ' if good else 'FIX'}   {msg}")

    print("\nChecking the video worker...\n")
    try:
        require_ffmpeg()
        line(True, "FFmpeg is installed")
    except UserFacingError as e:
        line(False, e.message)
    try:
        from .pipeline.tracking import FaceTrackingUnavailable, load_cv2
        load_cv2()
        line(True, "Face tracking (OpenCV) works")
    except FaceTrackingUnavailable as e:
        blocked = "Application Control" in str(e) or "blocked" in str(e).lower()
        line(False, "Face tracking (OpenCV) couldn't load"
             + (" because Windows Smart App Control blocked it." if blocked else f": {e}")
             + " Clips will still be made, but show the whole frame instead of following the face."
             + " Try: npm run setup:worker (installs a version Windows trusts more).")
    problems = s.problems()
    for p in problems:
        line(False, p)
    if problems:
        print("\nAdd the missing keys to .env, then run this check again.\n")
        return 1

    try:
        Db(s.supabase_url, s.supabase_secret_key).select("jobs", {"status": "queued"}, columns="id")
        line(True, "Connected to the Supabase database with the secret key")
    except DbError as e:
        hint = "run supabase/migrations/0002_pipeline.sql in the SQL Editor" if "PGRST2" in str(e) else \
            "check SUPABASE_SECRET_KEY in .env"
        line(False, f"Database check failed ({hint}). Details: {str(e)[:150]}")
    except httpx.HTTPError:
        line(False, "Couldn't reach Supabase. Check your internet connection.")

    if s.stt_provider == "groq":
        try:
            r = httpx.get("https://api.groq.com/openai/v1/models",
                          headers={"Authorization": f"Bearer {s.groq_api_key}"}, timeout=20)
            ids = [m["id"] for m in r.json().get("data", [])] if r.status_code == 200 else []
            line(r.status_code == 200, "Groq key works" if r.status_code == 200 else
                 f"Groq rejected the key (error {r.status_code}). Check GROQ_API_KEY.")
            if ids and s.groq_stt_model not in ids:
                line(False, f"Groq model '{s.groq_stt_model}' isn't available. Options: "
                            f"{', '.join(i for i in ids if 'whisper' in i)}")
        except httpx.HTTPError:
            line(False, "Couldn't reach Groq. Check your internet connection.")

    if s.llm_provider == "gemini":
        try:
            gem = make_llm(s, with_fallback=False)
            models = gem.list_models()
            line(True, "Gemini key works")
            ok_model, why = gem.works(s.gemini_model)
            if ok_model:
                line(True, f"Gemini model '{s.gemini_model}' answers")
            else:
                print(f"  ...   '{s.gemini_model}' didn't answer ({why}). Trying other models your key can use...")
                found = None
                for m in [m for m in gem.rank_candidates(models) if m != s.gemini_model][:8]:
                    if gem.works(m)[0]:
                        found = m
                        break
                if found:
                    line(False, f"Gemini model '{s.gemini_model}' isn't available to your key, but '{found}' works.\n"
                                f"        In .env, change the GEMINI_MODEL line to:   GEMINI_MODEL={found}")
                else:
                    line(False, f"No Gemini model answered. Models your key lists: {', '.join(models[:10])}")
        except httpx.HTTPStatusError as e:
            line(False, f"Gemini rejected the key (error {e.response.status_code}). Check GEMINI_API_KEY.")
        except httpx.HTTPError:
            line(False, "Couldn't reach Gemini. Check your internet connection.")

    if s.groq_api_key and (s.llm_provider == "groq" or s.llm_fallback == "groq"):
        from .providers.llm.groq import GroqLlm
        gq = GroqLlm(s.groq_api_key, s.groq_llm_model)
        role = "main AI" if s.llm_provider == "groq" else "backup AI (used when Gemini's free limit is reached)"
        try:
            if gq.works(s.groq_llm_model)[0]:
                line(True, f"Groq {role}: '{s.groq_llm_model}' answers")
            else:
                found = next((m for m in gq.rank_candidates(gq.list_models())[:8] if gq.works(m)[0]), None)
                line(False, f"Groq model '{s.groq_llm_model}' isn't available"
                            + (f", but '{found}' works.\n        In .env, add or change:   GROQ_LLM_MODEL={found}"
                               if found else "."))
        except httpx.HTTPError:
            line(False, "Couldn't check the Groq backup AI. Check your internet connection.")

    print("\nAll good! Start everything with: npm run dev\n" if ok else "\nFix the items above, then run this again.\n")
    return 0 if ok else 1


def main() -> int:
    _setup_logging()
    s = Settings.load()
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        return check(s)

    problems = s.problems()
    try:
        require_ffmpeg()
    except UserFacingError as e:
        problems.append(e.message)
    if problems:
        print("\n[worker] The video worker isn't set up yet, so videos won't be processed:")
        for p in problems:
            print(f"   - {p}")
        print("[worker] Fix these in .env, then stop (Ctrl + C) and run 'npm run dev' again.\n")
        return 0

    try:
        ctx = Ctx(settings=s, db=Db(s.supabase_url, s.supabase_secret_key),
                  storage=make_storage(s), stt=make_stt(s), llm=make_llm(s))
        loop(ctx, once="--once" in sys.argv)
    except ConfigError as e:
        print(f"[worker] {e}")
        return 1
    except DbError as e:
        print(f"[worker] Can't use the database: {e}\n"
              "[worker] Did you run supabase/migrations/0002_pipeline.sql? Is SUPABASE_SECRET_KEY right?")
        return 1
    except KeyboardInterrupt:
        print("\n[worker] stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
