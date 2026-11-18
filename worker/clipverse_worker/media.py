"""FFmpeg helpers: inspect a video, pull out audio, make a small proxy copy."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .errors import UserFacingError

NOT_A_VIDEO = ("We couldn't read this file as a video. Please upload an MP4, MOV, MKV or WEBM file "
               "that plays on your computer.")


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise UserFacingError("FFmpeg isn't installed on this computer, so videos can't be processed. "
                              "Install it (Windows: winget install Gyan.FFmpeg), then restart the app.")


def run(cmd: list[str], cwd: Path | None = None) -> str:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        tail = "\n".join(p.stderr.strip().splitlines()[-8:])
        raise RuntimeError(f"{Path(cmd[0]).name} failed ({p.returncode}): {tail}")
    return p.stdout + p.stderr


@dataclass
class VideoInfo:
    duration: float
    width: int   # as displayed (after phone rotation)
    height: int
    fps: float
    has_audio: bool


def probe(path: Path) -> VideoInfo:
    try:
        out = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
        data = json.loads(out[out.index("{"):])
    except (RuntimeError, ValueError) as e:
        raise UserFacingError(NOT_A_VIDEO) from e

    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"
                  and not (s.get("disposition") or {}).get("attached_pic")), None)
    if not video:
        raise UserFacingError(NOT_A_VIDEO)
    has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))

    w, h = int(video.get("width") or 0), int(video.get("height") or 0)
    rotation = 0
    for sd in video.get("side_data_list") or []:
        if "rotation" in sd:
            rotation = int(float(sd["rotation"]))
    rotation = int((video.get("tags") or {}).get("rotate", rotation))
    if abs(rotation) % 180 == 90:
        w, h = h, w

    num, _, den = str(video.get("avg_frame_rate") or "30/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 30.0
    duration = float((data.get("format") or {}).get("duration") or video.get("duration") or 0)
    if duration <= 0 or w <= 0 or h <= 0:
        raise UserFacingError(NOT_A_VIDEO)
    return VideoInfo(duration=duration, width=w, height=h, fps=fps or 30.0, has_audio=has_audio)


def probe_audio_duration(path: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return float(out.strip().splitlines()[0])


def extract_audio(src: Path, dest: Path) -> None:
    """16 kHz mono FLAC - what speech-to-text models expect, and small to upload."""
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "flac", str(dest)])


def find_silences(audio: Path, min_silence: float = 0.4, noise_db: int = -35) -> list[tuple[float, float]]:
    out = run(["ffmpeg", "-v", "info", "-i", str(audio), "-af",
               f"silencedetect=noise={noise_db}dB:d={min_silence}", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    return list(zip(starts, ends))


def plan_chunks(duration: float, max_len: float, silences: list[tuple[float, float]],
                search: float = 30.0) -> list[tuple[float, float]]:
    """Split [0, duration] into pieces <= max_len, cutting in the middle of a pause when we can,
    so no word gets chopped in half."""
    chunks, start = [], 0.0
    while duration - start > max_len:
        target = start + max_len
        mids = [(a + b) / 2 for a, b in silences if target - search <= (a + b) / 2 <= target]
        cut = max(mids) if mids else target
        chunks.append((start, cut))
        start = cut
    chunks.append((start, duration))
    return chunks


def cut_audio(src: Path, start: float, end: float, dest: Path) -> None:
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", str(src),
         "-c:a", "flac", str(dest)])


def make_proxy(src: Path, dest: Path, height: int = 480, fps: int = 10) -> None:
    """Small, low-frame-rate copy used only for face tracking (much faster to scan)."""
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-an",
         "-vf", f"fps={fps},scale=-2:{height}", "-c:v", "libx264", "-preset", "ultrafast",
         "-crf", "30", str(dest)])
