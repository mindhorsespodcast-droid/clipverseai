"""Renders one finished 1080x1920 clip with FFmpeg: crop (or fit) + burned-in captions."""
from __future__ import annotations

import shutil
from pathlib import Path

from ..config import FONTS_DIR
from ..media import VideoInfo, run

OUT_W, OUT_H = 1080, 1920


def crop_width(info: VideoInfo) -> int:
    return min(info.width, int(round(info.height * 9 / 16 / 2)) * 2)


def sendcmd_lines(points: list[tuple[float, float]], info: VideoInfo, duration: float, step: float = 1 / 15) -> str:
    """Turn the face track into "time crop x <pixels>;" commands, interpolated for smooth motion."""
    cw = crop_width(info)
    max_x = info.width - cw

    def x_at(t: float) -> int:
        if t <= points[0][0]:
            c = points[0][1]
        elif t >= points[-1][0]:
            c = points[-1][1]
        else:
            for (t0, c0), (t1, c1) in zip(points, points[1:]):
                if t0 <= t <= t1:
                    c = c0 + (c1 - c0) * ((t - t0) / (t1 - t0) if t1 > t0 else 0)
                    break
        return int(max(0, min(max_x, round(c * info.width - cw / 2))))

    lines, last, t = [], None, 0.0
    while t <= duration + step:
        x = x_at(t)
        if x != last:
            lines.append(f"{t:.3f} crop x {x};")
            last = x
        t += step
    return "\n".join(lines) + "\n"


def render_clip(source: Path, info: VideoInfo, start: float, end: float, track: dict,
                ass_text: str, work: Path) -> tuple[Path, Path]:
    """Returns (video, thumbnail) paths inside `work`."""
    work.mkdir(parents=True, exist_ok=True)
    duration = end - start
    (work / "captions.ass").write_text(ass_text, encoding="utf-8")
    # Copy fonts next to the job so FFmpeg never has to parse a tricky Windows path.
    fonts = work / "fonts"
    if not fonts.exists():
        shutil.copytree(FONTS_DIR, fonts)
    subs = "ass=captions.ass:fontsdir=fonts"

    use_crop = track.get("layout") == "crop" and track.get("points") and crop_width(info) < info.width
    if use_crop:
        (work / "crop.cmd").write_text(sendcmd_lines(track["points"], info, duration), encoding="utf-8")
        cw = crop_width(info)
        graph = (f"[0:v]sendcmd=f=crop.cmd,crop=w={cw}:h={info.height}:x=0:y=0,"
                 f"scale={OUT_W}:{OUT_H},setsar=1,{subs}[v]")
    else:
        graph = (f"[0:v]split=2[a][b];"
                 f"[a]scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,crop={OUT_W}:{OUT_H},"
                 f"boxblur=20:2,eq=brightness=-0.12[bg];"
                 f"[b]scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=decrease[fg];"
                 f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,{subs}[v]")

    tmp_out = work / "out.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
         "-i", str(source.resolve()), "-filter_complex", graph, "-map", "[v]", "-map", "0:a?",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "out.mp4"], cwd=work)
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{min(1.0, duration / 2):.2f}", "-i", "out.mp4",
         "-frames:v", "1", "-vf", "scale=540:-2", "-q:v", "4", "thumb.jpg"], cwd=work)
    return tmp_out, work / "thumb.jpg"
