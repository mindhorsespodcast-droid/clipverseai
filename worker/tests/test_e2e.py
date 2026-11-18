"""Runs the whole pipeline on a generated video with fake STT/LLM/DB.

Set CLIPVERSE_TEST_FACE=/path/to/face.jpg to put a moving face in the video
(then the clip should use the speaker-tracking crop instead of the fit layout).
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from clipverse_worker.config import Settings
from clipverse_worker.pipeline.process import Ctx
from clipverse_worker.providers.storage.local import LocalStorage
from clipverse_worker.worker import loop

from .fakes import FakeDb, FakeLlm, FakeStt

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

DURATION = 100


def make_video(path: Path, face: str | None) -> None:
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=0x2a3040:s=1920x1080:r=25:d={DURATION}",
           "-f", "lavfi", "-i", f"sine=frequency=220:duration={DURATION}"]
    if face:
        # face drifts from left to right across the frame
        cmd += ["-i", face, "-filter_complex",
                "[2:v]scale=360:-1[f];[0:v][f]overlay=x='100+t*12':y=300[v]", "-map", "[v]", "-map", "1:a"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(path)]
    subprocess.run(cmd, check=True)


def probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    storage = LocalStorage(tmp_path / "storage")
    db = FakeDb()
    face = os.getenv("CLIPVERSE_TEST_FACE")
    src_key = "projects/p1/source.mp4"
    src = storage.local_path(src_key)
    src.parent.mkdir(parents=True)
    make_video(src, face)
    db.insert("projects", {"id": "p1", "user_id": "u1", "title": "Test", "status": "queued", "content_type": "podcast",
                           "language": "hinglish", "caption_script": "roman", "source_path": src_key})
    db.insert("jobs", {"project_id": "p1", "user_id": "u1", "type": "process_project"})
    settings = Settings.load()
    settings = Settings(**{**settings.__dict__, "storage_dir": tmp_path / "storage", "max_clips": 3})
    llm = FakeLlm()
    ctx = Ctx(settings=settings, db=db, storage=storage, stt=FakeStt(), llm=llm)
    return ctx, db, storage, llm, bool(face)


def test_full_pipeline(setup):
    ctx, db, storage, llm, has_face = setup
    loop(ctx, once=True)

    project = db.select_one("projects", {"id": "p1"})
    assert project["status"] == "ready", project
    assert project["progress"]["cost_usd"] > 0

    transcript = db.select_one("transcripts", {"project_id": "p1"})
    assert len(transcript["words"]) > 50

    clips = db.select("clips", {"project_id": "p1"}, order="score.desc")
    assert 1 <= len(clips) <= 3
    for c in clips:
        assert c["status"] == "ready"
        out = c["outputs"]["roman"]
        video = storage.local_path(out["video"])
        assert video.exists() and storage.local_path(out["thumb"]).exists()
        info = probe(video)
        v = next(s for s in info["streams"] if s["codec_type"] == "video")
        assert (v["width"], v["height"]) == (1080, 1920)
        assert any(s["codec_type"] == "audio" for s in info["streams"])
        assert abs(float(info["format"]["duration"]) - (c["end_sec"] - c["start_sec"])) < 0.6
        assert c["crop_track"]["layout"] == ("crop" if has_face else "fit")
        assert any(w["roman"] == "90%" for w in c["words"]) or all(w["roman"] != "नब्बे" for w in c["words"])

    job = db.select("jobs", {"project_id": "p1"})[0]
    assert job["status"] == "done"
    assert job["minutes_processed"] == pytest.approx(DURATION / 60, abs=0.05)
    assert job["cost_breakdown"]["stt_audio_seconds"] == pytest.approx(DURATION, abs=1)
    assert db.select("usage_ledger", {"project_id": "p1"})[0]["minutes"] == pytest.approx(DURATION / 60, abs=0.05)

    # ask for the Devanagari version of the best clip
    best = clips[0]
    db.update("clips", {"id": best["id"]}, {"outputs": best["outputs"] | {"devanagari": {"status": "queued"}}})
    db.insert("jobs", {"project_id": "p1", "user_id": "u1", "type": "render_clip",
                       "payload": {"clip_id": best["id"], "script": "devanagari"}})
    calls_before = llm.calls.count("scripts")
    loop(ctx, once=True)
    best = db.select_one("clips", {"id": best["id"]})
    assert best["outputs"]["devanagari"]["status"] == "ready"
    assert best["outputs"]["roman"]["status"] == "ready"
    assert llm.calls.count("scripts") == calls_before  # reused saved words, no new LLM call
    os.environ.get("CLIPVERSE_KEEP") and shutil.copytree(storage.root, os.environ["CLIPVERSE_KEEP"], dirs_exist_ok=True)


def test_not_a_video_fails_with_plain_message(tmp_path):
    storage = LocalStorage(tmp_path / "s")
    db = FakeDb()
    bad = storage.local_path("projects/p2/source.mp4")
    bad.parent.mkdir(parents=True)
    bad.write_text("this is not a video")
    db.insert("projects", {"id": "p2", "user_id": "u1", "status": "queued", "source_path": "projects/p2/source.mp4"})
    db.insert("jobs", {"project_id": "p2", "user_id": "u1", "type": "process_project"})
    ctx = Ctx(settings=Settings.load(), db=db, storage=storage, stt=FakeStt(), llm=FakeLlm())
    loop(ctx, once=True)
    p = db.select_one("projects", {"id": "p2"})
    assert p["status"] == "failed"
    assert "couldn't read this file as a video" in p["error_message"]
    assert db.select("jobs", {"project_id": "p2"})[0]["status"] == "failed"


def test_clips_still_made_when_face_tracking_is_blocked(setup, monkeypatch):
    """Windows Smart App Control can block OpenCV; we must still deliver clips (fit layout)."""
    from clipverse_worker.pipeline import tracking

    def blocked():
        raise tracking.FaceTrackingUnavailable("DLL load failed: An Application Control policy has blocked this file.")

    monkeypatch.setattr(tracking, "load_cv2", blocked)
    ctx, db, storage, llm, _ = setup
    loop(ctx, once=True)
    assert db.select_one("projects", {"id": "p1"})["status"] == "ready"
    clips = db.select("clips", {"project_id": "p1"})
    assert clips and all(c["status"] == "ready" and c["crop_track"]["layout"] == "fit" for c in clips)


def test_hinglish_video_translated_by_whisper_is_retranscribed(setup):
    """If Whisper answers a Hinglish video in English, the worker retries and keeps the Hindi."""
    from clipverse_worker.providers.stt.base import SttResult, Word

    ctx, db, *_ = setup
    real = ctx.stt
    calls = []

    class TranslatingStt:
        name, model, max_chunk_seconds = real.name, real.model, real.max_chunk_seconds

        def transcribe(self, audio, language, prompt):
            calls.append((language, prompt))
            res = real.transcribe(audio, language, prompt)
            if language == "hi":  # first try: English "translation"
                return SttResult(words=[Word("word", w.start, w.end) for w in res.words],
                                 segments=res.segments, language="english")
            return res

    ctx.stt = TranslatingStt()
    loop(ctx, once=True)
    words = db.select_one("transcripts", {"project_id": "p1"})["words"]
    assert sum(1 for w in words if w["w"] != "word") / len(words) > 0.5
    assert calls[0][0] == "hi" and calls[0][1] and "दोस्तों" in calls[0][1]  # Hinglish prompt was sent
    assert any(lang is None for lang, _ in calls)  # retried with auto-detect
