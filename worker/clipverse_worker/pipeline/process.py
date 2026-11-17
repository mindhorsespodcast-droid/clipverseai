"""The full pipeline for one project (brief section 8).

  1. check the video  ->  2. transcript  ->  3. find moments  ->  4. per clip: track face,
  caption scripts, render  ->  5. usage + cost log.

Every step saves its result before moving on, so a retry (after a free-tier limit,
a crash, or the laptop sleeping) continues where it stopped instead of starting over.
One failed clip never fails the whole project.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from .. import media
from ..config import Settings
from ..errors import RetryLater, UserFacingError
from . import moments as moments_mod
from .captions import build_ass
from .cost import Cost
from .render import render_clip
from .scripts import convert_words
from .tracking import track_clip

log = logging.getLogger("worker")

STT_LANGUAGE = {"hi": "hi", "hinglish": "hi", "en": "en", "auto": None}


@dataclass
class Ctx:
    settings: Settings
    db: Any
    storage: Any
    stt: Any
    llm: Any


# ---------------------------------------------------------------- helpers

def _set_project(ctx: Ctx, pid: str, **values) -> None:
    ctx.db.update("projects", {"id": pid}, values)


def _progress(ctx: Ctx, pid: str, status: str, detail: str) -> None:
    log.info("[%s] %s", pid[:8], detail)
    _set_project(ctx, pid, status=status, progress={"detail": detail})


def _save_cost(ctx: Ctx, job: dict, cost: Cost, minutes: float | None = None) -> None:
    values = {"cost_breakdown": cost.as_dict(), "cost_estimate_usd": round(cost.total_usd, 6)}
    if minutes is not None:
        values["minutes_processed"] = round(minutes, 3)
    ctx.db.update("jobs", {"id": job["id"]}, values)


def _work(ctx: Ctx, pid: str):
    return ctx.storage.work_dir(f"projects/{pid}/work")


def segments_from_words(words: list[dict], max_len: float = 20.0, pause: float = 0.8) -> list[dict]:
    """Fallback when the provider gives no sentences: break at pauses or every ~20 s."""
    segs, cur = [], []
    for w in words:
        if cur and (w["start"] - cur[-1]["end"] > pause or w["end"] - cur[0]["start"] > max_len):
            segs.append(cur)
            cur = []
        cur.append(w)
    if cur:
        segs.append(cur)
    return [{"start": s[0]["start"], "end": s[-1]["end"], "text": " ".join(w["w"] for w in s)} for s in segs]


def split_long_segments(segments: list[dict], words: list[dict], max_len: float = 20.0) -> list[dict]:
    """Whisper 'segments' can be 30 s long; split those at the biggest pauses so clip edges stay flexible."""
    out = []
    for seg in segments:
        if seg["end"] - seg["start"] <= max_len:
            out.append(seg)
            continue
        inner = [w for w in words if seg["start"] - 0.05 <= (w["start"] + w["end"]) / 2 <= seg["end"] + 0.05]
        if len(inner) < 2:
            out.append(seg)
            continue
        out.extend(segments_from_words(inner, max_len=max_len, pause=0.5))
    return out


# ---------------------------------------------------------------- step 2: transcript

def transcribe(ctx: Ctx, project: dict, source, info: media.VideoInfo, cost: Cost, job: dict) -> dict:
    pid = project["id"]
    work = _work(ctx, pid)
    audio = work / "audio.flac"
    _progress(ctx, pid, "transcribing", "Getting the audio ready")
    if not audio.exists():
        media.extract_audio(source, audio)

    chunks = media.plan_chunks(info.duration, ctx.stt.max_chunk_seconds, media.find_silences(audio))
    language = STT_LANGUAGE.get(project.get("language") or "auto")
    words, segments, detected = [], [], None
    for k, (a, b) in enumerate(chunks, start=1):
        part_file = work / f"stt_part_{k}.json"
        if part_file.exists():  # already done on an earlier attempt
            part = json.loads(part_file.read_text(encoding="utf-8"))
        else:
            _progress(ctx, pid, "transcribing",
                      f"Transcribing part {k} of {len(chunks)}" if len(chunks) > 1 else "Transcribing")
            piece = work / f"chunk_{k}.flac"
            media.cut_audio(audio, a, b, piece)
            res = ctx.stt.transcribe(piece, language, None)
            piece.unlink(missing_ok=True)
            cost.add_stt(getattr(ctx.stt, "model", ctx.stt.name), b - a)
            _save_cost(ctx, job, cost)
            part = {
                "language": res.language,
                "words": [{"w": w.text, "start": round(w.start + a, 3), "end": round(w.end + a, 3),
                           "speaker": w.speaker} for w in res.words],
                "segments": [{"start": round(s.start + a, 3), "end": round(s.end + a, 3), "text": s.text}
                             for s in res.segments],
            }
            part_file.write_text(json.dumps(part, ensure_ascii=False), encoding="utf-8")
        words += part["words"]
        segments += part["segments"] or segments_from_words(part["words"])
        detected = detected or part["language"]

    if len(words) < 5:
        raise UserFacingError("We couldn't hear any speech in this video, so there's nothing to clip yet. "
                              "Check that the video has sound with people talking.")
    segments = split_long_segments(segments, words)
    row = {"project_id": pid, "provider": ctx.stt.name, "language": detected, "words": words, "segments": segments}
    ctx.db.insert("transcripts", row)
    audio.unlink(missing_ok=True)
    return row


# ---------------------------------------------------------------- step 4: one clip

def clip_words(transcript: dict, start: float, end: float) -> list[dict]:
    return [{"start": w["start"], "end": w["end"], "text": w["w"]} for w in transcript["words"]
            if w["start"] >= start - 0.05 and w["end"] <= end + 0.05]


def render_one(ctx: Ctx, project: dict, clip: dict, script: str, transcript: dict, source,
               info: media.VideoInfo, cost: Cost, job: dict) -> None:
    pid, cid = project["id"], clip["id"]
    start, end = float(clip["start_sec"]), float(clip["end_sec"])
    work = ctx.storage.work_dir(f"projects/{pid}/work/clip-{cid}")

    def set_output(state: dict) -> None:
        fresh = ctx.db.select_one("clips", {"id": cid}) or clip
        outputs = dict(fresh.get("outputs") or {})
        outputs[script] = state
        values = {"outputs": outputs}
        if script == project.get("caption_script", "roman"):
            values["status"] = {"ready": "ready", "failed": "failed"}.get(state["status"], "rendering")
        ctx.db.update("clips", {"id": cid}, values)
        clip["outputs"] = outputs

    set_output({"status": "rendering"})

    if not clip.get("crop_track"):
        proxy = _work(ctx, pid) / "proxy.mp4"
        if not proxy.exists():
            media.make_proxy(source, proxy)
        track = track_clip(proxy, start, end)
        ctx.db.update("clips", {"id": cid}, {"crop_track": track, "layout": track["layout"]})
        clip["crop_track"] = track

    if not clip.get("words"):
        words, usage, _ = convert_words(ctx.llm, clip_words(transcript, start, end))
        cost.add_llm(ctx.llm.model, usage)
        _save_cost(ctx, job, cost)
        ctx.db.update("clips", {"id": cid}, {"words": words})
        clip["words"] = words

    rel = [w | {"start": max(0.0, w["start"] - start), "end": max(0.0, w["end"] - start)} for w in clip["words"]]
    ass = build_ass(rel, script, end - start)
    video, thumb = render_clip(source, info, start, end, clip["crop_track"], ass, work)

    vkey = f"projects/{pid}/clips/{cid}-{script}.mp4"
    tkey = f"projects/{pid}/clips/{cid}-{script}.jpg"
    ctx.storage.put_file(video, vkey)
    ctx.storage.put_file(thumb, tkey)
    ctx.storage.delete(f"projects/{pid}/work/clip-{cid}")
    set_output({"status": "ready", "video": vkey, "thumb": tkey})


def _render_safely(ctx, project, clip, script, transcript, source, info, cost, job) -> bool:
    try:
        render_one(ctx, project, clip, script, transcript, source, info, cost, job)
        return True
    except RetryLater:
        raise  # a free-tier limit: pause the whole job and come back
    except Exception as e:  # noqa: BLE001 - one bad clip must not sink the project
        log.exception("[%s] clip %s failed", project["id"][:8], clip["id"][:8])
        msg = e.message if isinstance(e, UserFacingError) else "We couldn't make this clip. Try again later."
        fresh = ctx.db.select_one("clips", {"id": clip["id"]}) or clip
        outputs = dict(fresh.get("outputs") or {})
        outputs[script] = {"status": "failed", "error": msg}
        values = {"outputs": outputs, "error": str(e)[:500]}
        if script == project.get("caption_script", "roman"):
            values["status"] = "failed"
        ctx.db.update("clips", {"id": clip["id"]}, values)
        return False


# ---------------------------------------------------------------- jobs

def _load_source(ctx: Ctx, project: dict):
    key = project.get("source_path")
    if not key or not ctx.storage.exists(key):
        raise UserFacingError("The uploaded video file is missing. Please upload it again.")
    source = ctx.storage.local_path(key)
    info = media.probe(source)
    return source, info


def process_project(ctx: Ctx, job: dict) -> None:
    s = ctx.settings
    project = ctx.db.select_one("projects", {"id": job["project_id"]})
    if not project:
        return  # deleted meanwhile
    pid = project["id"]
    cost = Cost.from_job(job)
    script = project.get("caption_script") or "roman"

    _progress(ctx, pid, "transcribing", "Checking your video")
    source, info = _load_source(ctx, project)
    if info.duration > s.max_video_hours * 3600:
        raise UserFacingError(f"This video is longer than {s.max_video_hours} hours. "
                              "Please upload a shorter video or split it into parts.")
    if info.duration < s.clip_min_sec + 5:
        raise UserFacingError(f"This video is too short. Upload at least {s.clip_min_sec + 5} seconds of video.")
    if not info.has_audio:
        raise UserFacingError("This video has no sound. ClipVerse AI finds moments from what people say, "
                              "so it needs a video with speech.")
    _set_project(ctx, pid, source_duration_sec=round(info.duration, 3))

    # 2. transcript
    transcript = ctx.db.select_one("transcripts", {"project_id": pid})
    if not transcript:
        transcript = transcribe(ctx, project, source, info, cost, job)

    # 3. moments
    clips = ctx.db.select("clips", {"project_id": pid}, order="score.desc")
    if not clips:
        _progress(ctx, pid, "finding_clips", "Finding the best moments")
        found, usage = moments_mod.find_moments(
            ctx.llm, transcript["segments"], project.get("content_type") or "other", info.duration,
            s.clip_min_sec, s.clip_max_sec, s.max_clips)
        cost.add_llm(ctx.llm.model, usage)
        _save_cost(ctx, job, cost)
        if not found:
            raise UserFacingError("We couldn't find moments worth clipping in this video. "
                                  "Try a video with more talking, or a different content type.")
        clips = ctx.db.insert("clips", [{
            "project_id": pid, "start_sec": m.start, "end_sec": m.end, "score": m.score,
            "title": m.title, "reason": m.reason, "caption_script": script,
            "outputs": {script: {"status": "queued"}},
        } for m in found])
        clips.sort(key=lambda c: -c["score"])

    # 4. render each clip (skip ones already done)
    todo = [c for c in clips if (c.get("outputs") or {}).get(script, {}).get("status") != "ready"]
    done = len(clips) - len(todo)
    for c in todo:
        done += 1
        _progress(ctx, pid, "rendering", f"Making clip {done} of {len(clips)}")
        _render_safely(ctx, project, c, script, transcript, source, info, cost, job)

    # 5. wrap up
    final = ctx.db.select("clips", {"project_id": pid})
    ready = sum(1 for c in final if (c.get("outputs") or {}).get(script, {}).get("status") == "ready")
    minutes = info.duration / 60
    _save_cost(ctx, job, cost, minutes)
    if not ctx.db.select("usage_ledger", {"project_id": pid, "reason": "processing"}):
        ctx.db.insert("usage_ledger", {"user_id": project["user_id"], "project_id": pid,
                                       "minutes": round(minutes, 3), "reason": "processing"})
    if ready == 0:
        raise UserFacingError("We found moments but couldn't make any clips. Please try again.")
    per_min = cost.total_usd / minutes if minutes else 0
    _set_project(ctx, pid, status="ready", error_message=None,
                 progress={"detail": f"{ready} clips ready", "cost_usd": round(cost.total_usd, 5),
                           "cost_usd_per_min": round(per_min, 6)})
    log.info("[%s] done: %d clips, est. cost $%.4f ($%.5f per video minute)", pid[:8], ready,
             cost.total_usd, per_min)


def render_clip_job(ctx: Ctx, job: dict) -> None:
    """A user asked for another caption script (e.g. Devanagari) of one clip."""
    payload = job.get("payload") or {}
    clip = ctx.db.select_one("clips", {"id": payload.get("clip_id")})
    if not clip:
        return
    project = ctx.db.select_one("projects", {"id": clip["project_id"]})
    transcript = ctx.db.select_one("transcripts", {"project_id": clip["project_id"]})
    if not project or not transcript:
        return
    cost = Cost.from_job(job)
    source, info = _load_source(ctx, project)
    _render_safely(ctx, project, clip, payload.get("script", "roman"), transcript, source, info, cost, job)
    _save_cost(ctx, job, cost)
