from clipverse_worker.media import VideoInfo, plan_chunks
from clipverse_worker.pipeline.captions import build_ass, group_phrases
from clipverse_worker.pipeline.moments import Moment, dedupe, parse_moments, target_count, windows
from clipverse_worker.pipeline.render import crop_width, sendcmd_lines
from clipverse_worker.pipeline.scripts import convert_words
from clipverse_worker.pipeline.tracking import pick_track, smooth
from clipverse_worker.providers.llm.gemini import parse_json

from .fakes import FakeLlm


def segs(n, length=5.0):
    return [{"start": i * length, "end": i * length + length - 0.2, "text": f"s{i}"} for i in range(n)]


def test_plan_chunks_cuts_in_pauses():
    chunks = plan_chunks(1500, 600, [(580.0, 581.0), (1190.0, 1191.0)])
    assert chunks == [(0.0, 580.5), (580.5, 1180.5), (1180.5, 1500)] or chunks[0] == (0.0, 580.5)
    assert all(b - a <= 600 for a, b in chunks)
    assert chunks[-1][1] == 1500


def test_plan_chunks_short_audio_is_one_chunk():
    assert plan_chunks(100, 600, []) == [(0.0, 100)]


def test_windows_overlap_and_cover_everything():
    s = segs(400)  # 2000 s
    w = windows(s)
    assert len(w) >= 3
    assert w[0][0] == 0 and w[-1][-1] == 399


def test_parse_moments_fits_length_and_rejects_bad_ids():
    s = segs(40)  # 5 s each
    answer = {"clips": [
        {"start_segment": 2, "end_segment": 30, "score": 80, "title": "too long", "reason": "r"},  # 145 s
        {"start_segment": 5, "end_segment": 5, "score": 70, "title": "too short", "reason": "r"},
        {"start_segment": 99, "end_segment": 100, "score": 99, "title": "bad", "reason": "r"},
        {"start_segment": "x", "end_segment": 3},
    ]}
    ms = parse_moments(answer, s, set(range(40)), 15, 90)
    assert len(ms) == 2
    for m in ms:
        assert 15 <= m.duration <= 90
        assert any(abs(m.start - x["start"]) < 1e-6 for x in s)
        assert any(abs(m.end - x["end"]) < 1e-6 for x in s)


def test_dedupe_keeps_best_of_overlapping():
    a = Moment(0, 40, 60, "a", "")
    b = Moment(5, 45, 90, "b", "")
    c = Moment(100, 140, 50, "c", "")
    kept = dedupe([a, b, c])
    assert [m.title for m in kept] == ["b", "c"]


def test_target_count():
    assert target_count(600, 10) == 4
    assert target_count(3600 * 3, 10) == 10
    assert target_count(60, 10) == 3


def test_captions_phrases_and_highlight():
    words = [{"start": i * 0.4, "end": i * 0.4 + 0.3, "text": t, "roman": r, "devanagari": d, "hl": h}
             for i, (t, r, d, h) in enumerate([
                 ("नब्बे", "90%", "90%", True), ("प्रतिशत", "", "", False), ("creators", "creators", "क्रिएटर्स", False),
                 ("यह", "yeh", "यह", False), ("गलती", "galti", "गलती", False), ("करते", "karte", "करते", False),
                 ("हैं।", "hain.", "हैं।", False)])]
    phrases = group_phrases(words, "roman")
    assert all(len(p) <= 3 for p in phrases)
    shown = [w["_t"] for p in phrases for w in p]
    assert "" not in shown and "प्रतिशत" not in shown  # blanked word stays hidden
    ass = build_ass(words, "devanagari", 5)
    assert "Noto Sans Devanagari" in ass and "क्रिएटर्स" in ass
    assert "&H003D6BFF" in ass  # accent on the highlighted number
    assert "Dialogue: 0,0:00:00.00" in ass


def test_convert_words_falls_back_when_llm_misbehaves():
    words = [{"start": 0, "end": 0.3, "text": "हैलो"}, {"start": 0.4, "end": 0.6, "text": "₹200"}]
    out, _, ok = convert_words(FakeLlm(fail_scripts=True), words)
    assert not ok
    assert [w["roman"] for w in out] == ["हैलो", "₹200"]
    assert out[1]["hl"] is True


def test_tracking_smooth_ignores_jitter_and_snaps_on_cuts():
    track = [(i * 0.2, 0.5 + (0.01 if i % 2 else -0.01)) for i in range(10)]
    track += [(2 + i * 0.2, 0.85) for i in range(10)]   # camera cut to another person
    out = smooth(track)
    assert all(abs(x - 0.5) < 0.02 for _, x in out[:10])
    assert abs(out[-1][1] - 0.85) < 0.01


def test_pick_track_prefers_current_face():
    samples = [(0.0, [(0.3, 0.05), (0.7, 0.04)]), (0.2, [(0.31, 0.04), (0.7, 0.05)])]
    assert [round(x, 2) for _, x in pick_track(samples)] == [0.3, 0.31]


def test_sendcmd_stays_inside_frame():
    info = VideoInfo(duration=60, width=1920, height=1080, fps=30, has_audio=True)
    assert crop_width(info) == 608
    lines = sendcmd_lines([(0, 0.0), (2, 1.0)], info, 2)
    xs = [int(line.split()[-1].rstrip(";")) for line in lines.strip().splitlines()]
    assert xs[0] == 0 and xs[-1] == 1920 - 608
    assert xs == sorted(xs)


def test_parse_json_handles_code_fences():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_titles_have_no_emoji_but_keep_hindi():
    from clipverse_worker.pipeline.moments import clean_text
    assert clean_text("GTA 6 NPC Details Are Insane! 🤯") == "GTA 6 NPC Details Are Insane!"
    assert clean_text("Graphics Comparison 🔥") == "Graphics Comparison"
    assert clean_text("यह गलती 90% क्रिएटर्स करते हैं ✨") == "यह गलती 90% क्रिएटर्स करते हैं"


class _TranslatingThenGoodLlm:
    """First answer translates Hindi into English (the bug Dyna saw); second answer is correct."""
    model = "fake"

    def __init__(self):
        self.calls = 0

    def complete_json(self, task, system, prompt):
        from clipverse_worker.providers.llm.base import LlmUsage
        self.calls += 1
        n = len([ln for ln in prompt.splitlines() if ln[:1].isdigit() and ": " in ln])
        if self.calls == 1:
            return {"roman": ["I", "explained", "that", "this", "is", "the"][:n] + ["x"] * max(0, n - 6),
                    "devanagari": ["ड"] * n}, LlmUsage()
        assert "rejected" in prompt
        return {"roman": ["maine", "samjhaya", "ki", "yeh", "habit", "hai"][:n], "devanagari": ["ड"] * n}, LlmUsage()


def test_translated_roman_is_rejected_and_retried():
    words = [{"start": i, "end": i + 0.5, "text": t} for i, t in enumerate(["मैंने", "समझाया", "कि", "यह", "habit", "है"])]
    llm = _TranslatingThenGoodLlm()
    out, _, ok = convert_words(llm, words)
    assert ok and llm.calls == 2
    assert [w["roman"] for w in out] == ["maine", "samjhaya", "ki", "yeh", "habit", "hai"]


def test_rate_limit_during_captions_pauses_instead_of_falling_back():
    import pytest
    from clipverse_worker.errors import RetryLater

    class Limited:
        model = "fake"

        def complete_json(self, *a):
            raise RetryLater(30, "limit")

    with pytest.raises(RetryLater):
        convert_words(Limited(), [{"start": 0, "end": 1, "text": "है"}])


def test_translation_detector():
    from clipverse_worker.pipeline.process import devanagari_share, looks_translated
    english = [{"w": w} for w in ("I explained that this habit changes everything for students who " * 3).split()]
    hindi = [{"w": w} for w in ("मैंने समझाया कि यह habit सब कुछ बदल देती है students के लिए " * 3).split()]
    assert looks_translated("hinglish", english)
    assert not looks_translated("hinglish", hindi)
    assert not looks_translated("en", english)
    assert devanagari_share(hindi) > 0.5
