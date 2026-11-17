"""Speaker tracking: find the main face over time so the 9:16 crop can follow it.

Runs on the small proxy video (480p, 10 fps) for speed. Output is a list of
(time, face-centre-x as 0..1 of the frame width), smoothed like a calm camera
operator: it ignores tiny head movements, glides to follow real movement, and
jumps instantly on a camera cut. If there's no face most of the time, we use
the "fit" layout (whole frame over a blurred background) instead of cropping.
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
import cv2  # noqa: E402

from ..config import FACE_MODEL  # noqa: E402

SAMPLE_EVERY = 0.2      # seconds between face checks
MIN_FACE_SHARE = 0.35   # need a face in >=35% of checks to use the crop layout
DEAD_ZONE = 0.04        # ignore movements smaller than 4% of frame width
FOLLOW = 0.25           # how quickly the window glides toward the face
CUT_JUMP = 0.22         # a jump this big for 2 checks in a row = camera cut, snap to it


def detect_faces(proxy: Path, start: float, end: float) -> list[tuple[float, list[tuple[float, float]]]]:
    """[(t relative to start, [(centre_x 0..1, area 0..1), ...]), ...]"""
    cap = cv2.VideoCapture(str(proxy))
    if not cap.isOpened():
        raise RuntimeError("Couldn't open the proxy video for face tracking")
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    detector = cv2.FaceDetectorYN.create(str(FACE_MODEL), "", (w, h), 0.6, 0.3, 50)
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)

    samples, next_t = [], start
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        if t > end:
            break
        if t + 1e-3 < next_t:
            continue
        next_t = t + SAMPLE_EVERY
        _, faces = detector.detect(frame)
        found = []
        if faces is not None:
            for f in faces:
                fx, _, fw, fh = (float(v) for v in f[:4])
                found.append(((fx + fw / 2) / w, (fw * fh) / (w * h)))
        samples.append((max(0.0, t - start), found))
    cap.release()
    return samples


def pick_track(samples: list[tuple[float, list[tuple[float, float]]]]) -> list[tuple[float, float | None]]:
    """Choose one face per sample: the biggest, but prefer the one we were already following."""
    track, last = [], None
    for t, faces in samples:
        if not faces:
            track.append((t, None))
            continue
        def weight(face):
            sticky = 1.6 if last is not None and abs(face[0] - last) < 0.1 else 1.0
            return face[1] * sticky
        cx = max(faces, key=weight)[0]
        track.append((t, cx))
        last = cx
    return track


def smooth(track: list[tuple[float, float | None]]) -> list[tuple[float, float]]:
    xs = [x for _, x in track]
    first = next((x for x in xs if x is not None), 0.5)
    filled, prev = [], first
    for x in xs:
        prev = x if x is not None else prev
        filled.append(prev)

    out, cur, pending = [], filled[0], 0
    for (t, _), target in zip(track, filled):
        diff = target - cur
        if abs(diff) > CUT_JUMP:
            pending += 1
            if pending >= 2:
                cur, pending = target, 0
        else:
            pending = 0
            if abs(diff) > DEAD_ZONE:
                cur += diff * FOLLOW
        out.append((round(t, 3), round(cur, 4)))
    return out


def track_clip(proxy: Path, start: float, end: float) -> dict:
    samples = detect_faces(proxy, start, end)
    if not samples:
        return {"layout": "fit", "points": []}
    with_face = sum(1 for _, f in samples if f)
    if with_face / len(samples) < MIN_FACE_SHARE:
        return {"layout": "fit", "points": [], "face_share": round(with_face / len(samples), 2)}
    return {"layout": "crop", "points": smooth(pick_track(samples)),
            "face_share": round(with_face / len(samples), 2)}
