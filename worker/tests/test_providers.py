"""Checks the REAL provider code builds valid requests and reads real-shaped answers
(network replaced by httpx.MockTransport - no keys needed)."""
import json

import httpx
import pytest

from clipverse_worker.errors import RetryLater, UserFacingError
from clipverse_worker.providers.llm.gemini import GeminiLlm
from clipverse_worker.providers.stt.groq import GroqStt

GROQ_ANSWER = {
    "text": "Namaste dosto aaj hum baat karenge.",
    "language": "hindi",
    "duration": 3.2,
    "segments": [{"id": 0, "start": 0.0, "end": 3.1, "text": " नमस्ते दोस्तों आज हम बात करेंगे।"}],
    "words": [{"word": "नमस्ते", "start": 0.0, "end": 0.5}, {"word": "दोस्तों", "start": 0.5, "end": 1.0},
              {"word": " ", "start": 1.0, "end": 1.0}],
}


def test_groq_sends_valid_multipart_and_parses_answer(tmp_path):
    seen = {}

    def handler(request: httpx.Request):
        body = request.read()
        seen["auth"] = request.headers["authorization"]
        seen["body"] = body
        seen["ctype"] = request.headers["content-type"]
        return httpx.Response(200, json=GROQ_ANSWER)

    audio = tmp_path / "chunk_1.flac"
    audio.write_bytes(b"fLaC fake audio")
    stt = GroqStt("gsk_test", "whisper-large-v3", client=httpx.Client(transport=httpx.MockTransport(handler)))
    res = stt.transcribe(audio, "hi", None)

    assert seen["auth"] == "Bearer gsk_test"
    assert seen["ctype"].startswith("multipart/form-data")
    body = seen["body"]
    assert body.count(b'name="timestamp_granularities[]"') == 2
    for field in (b'name="model"', b"whisper-large-v3", b'name="language"', b'name="response_format"',
                  b"verbose_json", b'filename="chunk_1.flac"', b"fLaC fake audio"):
        assert field in body
    assert [w.text for w in res.words] == ["नमस्ते", "दोस्तों"]  # blank word dropped
    assert res.segments[0].text.startswith("नमस्ते")


def test_groq_rate_limit_means_wait(tmp_path):
    audio = tmp_path / "a.flac"
    audio.write_bytes(b"x")
    stt = GroqStt("k", "m", client=httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(429, headers={"retry-after": "120"}, json={}))))
    with pytest.raises(RetryLater) as e:
        stt.transcribe(audio, None, None)
    assert e.value.seconds == 120


def test_groq_bad_key_is_plain_english(tmp_path):
    audio = tmp_path / "a.flac"
    audio.write_bytes(b"x")
    stt = GroqStt("k", "m", client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401, json={}))))
    with pytest.raises(UserFacingError, match="GROQ_API_KEY"):
        stt.transcribe(audio, None, None)


def test_gemini_request_and_answer():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["key"] = request.headers["x-goog-api-key"]
        seen["json"] = json.loads(request.read())
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [
                {"text": "thinking...", "thought": True},
                {"text": '```json\n{"clips": [{"start_segment": 1, "end_segment": 4, "score": 82.5}]}\n```'}]}}],
            "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 50, "thoughtsTokenCount": 200},
        })

    llm = GeminiLlm("AIza_test", "gemini-2.5-flash", client=httpx.Client(transport=httpx.MockTransport(handler)))
    answer, usage = llm.complete_json("moments", "system text", "prompt text")
    assert seen["url"].endswith("/models/gemini-2.5-flash:generateContent")
    assert seen["key"] == "AIza_test"
    assert seen["json"]["generationConfig"]["responseMimeType"] == "application/json"
    assert seen["json"]["systemInstruction"]["parts"][0]["text"] == "system text"
    assert answer["clips"][0]["score"] == 82.5
    assert (usage.input_tokens, usage.output_tokens) == (1000, 250)


def test_gemini_rate_limit_reads_retry_delay():
    body = {"error": {"code": 429, "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "37s"}]}}
    llm = GeminiLlm("k", "m", client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429, json=body))))
    with pytest.raises(RetryLater) as e:
        llm.complete_json("moments", "s", "p")
    assert e.value.seconds == 37


def test_moment_scores_as_decimals_or_text_are_accepted():
    from clipverse_worker.pipeline.moments import parse_moments
    segs = [{"start": i * 5.0, "end": i * 5.0 + 4.8, "text": "x"} for i in range(20)]
    ms = parse_moments({"clips": [{"start_segment": "S2", "end_segment": 8, "score": "82.5", "title": "t"}]},
                       segs, set(range(20)), 15, 90)
    assert len(ms) == 1 and ms[0].score == 82
