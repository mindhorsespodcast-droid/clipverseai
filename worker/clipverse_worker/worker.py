"""The worker loop: take the next job from the database, run it, record the outcome."""
from __future__ import annotations

import logging
import time
import traceback
from datetime import datetime, timedelta, timezone

from .errors import RetryLater, UserFacingError
from .pipeline.process import Ctx, process_project, render_clip_job

log = logging.getLogger("worker")

HANDLERS = {"process_project": process_project, "render_clip": render_clip_job}
GENERIC_ERROR = ("Something went wrong while processing this video. We tried a few times and it still "
                 "failed. Please try again; if it keeps happening, the details are in the worker window.")


def _later(seconds: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def run_job(ctx: Ctx, job: dict) -> None:
    db, pid = ctx.db, job.get("project_id")
    started = time.monotonic()
    try:
        HANDLERS[job["type"]](ctx, job)
        db.update("jobs", {"id": job["id"]}, {"status": "done", "error": None, "locked_at": None})
        log.info("job %s (%s) finished in %.0fs", job["id"][:8], job["type"], time.monotonic() - started)

    except RetryLater as e:
        log.warning("job %s waiting %.0fs: %s", job["id"][:8], e.seconds, e.reason)
        # waiting for a free-tier limit doesn't use up a retry attempt
        db.update("jobs", {"id": job["id"]}, {"status": "queued", "locked_at": None, "run_after": _later(e.seconds),
                                              "attempts": max(0, job["attempts"] - 1), "error": e.reason})
        if pid and job["type"] == "process_project":
            db.update("projects", {"id": pid}, {"progress": {
                "detail": f"Paused: {e.reason}. Continuing automatically in about {max(1, round(e.seconds / 60))} min."}})

    except Exception as e:  # noqa: BLE001
        user_facing = isinstance(e, UserFacingError)
        if user_facing:
            log.warning("job %s: %s", job["id"][:8], e.message)
        else:
            log.exception("job %s failed (attempt %s of %s)", job["id"][:8], job["attempts"], job["max_attempts"])
        retry = not user_facing and job["attempts"] < job["max_attempts"]
        detail = traceback.format_exc()[-2000:]
        if retry:
            db.update("jobs", {"id": job["id"]}, {"status": "queued", "locked_at": None, "error": detail,
                                                  "run_after": _later(30 * job["attempts"])})
            return
        db.update("jobs", {"id": job["id"]}, {"status": "failed", "locked_at": None, "error": detail})
        if pid and job["type"] == "process_project":
            db.update("projects", {"id": pid}, {"status": "failed", "progress": {},
                                                "error_message": e.message if user_facing else GENERIC_ERROR})


def loop(ctx: Ctx, once: bool = False) -> None:
    moved = ctx.db.rpc("requeue_stale_jobs", {"p_older_than_minutes": 0})
    if moved:
        log.info("picked up %s unfinished job(s) from last time", moved)
    # Jobs paused for a free-tier limit: a restart means "try again now" (settings may have changed).
    woken = ctx.db.update("jobs", {"status": "queued"}, {"run_after": datetime.now(timezone.utc).isoformat()})
    if woken:
        log.info("%s waiting job(s) will be tried again now", len(woken))
    log.info("ready - waiting for videos (checking every %.0fs)", ctx.settings.poll_seconds)
    while True:
        jobs = ctx.db.rpc("claim_job")
        if jobs:
            run_job(ctx, jobs[0])
            continue
        if once:
            return
        time.sleep(ctx.settings.poll_seconds)
