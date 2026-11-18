"""Google Gemini (free tier, rate-limited). Docs: ai.google.dev/api/generate-content

Free-tier note: Google may use free-tier prompts to improve its products, so only
send our own test videos through it (see DECISIONS.md).
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from ...errors import RetryLater, UserFacingError
from .base import LlmUsage

BASE = "https://generativelanguage.googleapis.com/v1beta"


def parse_json(text: str) -> Any:
    text = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    if fenced:
        text = fenced.group(1)
    return json.loads(text)


def _retry_delay(body: dict) -> float:
    for d in (body.get("error") or {}).get("details") or []:
        delay = d.get("retryDelay")
        if isinstance(delay, str) and delay.endswith("s"):
            try:
                return float(delay[:-1])
            except ValueError:
                pass
    return 60.0


class GeminiLlm:
    name = "gemini"

    def __init__(self, api_key: str, model: str, client: httpx.Client | None = None):
        self.api_key = api_key
        self.model = model
        self._http = client or httpx.Client(timeout=180)

    def complete_json(self, task: str, system: str, prompt: str) -> tuple[Any, LlmUsage]:
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.4},
        }
        try:
            res = self._http.post(
                f"{BASE}/models/{self.model}:generateContent",
                headers={"x-goog-api-key": self.api_key},
                json=payload,
            )
        except httpx.HTTPError as e:
            raise RetryLater(60, f"Couldn't reach Gemini ({e.__class__.__name__})") from e

        if res.status_code == 429:
            raise RetryLater(_retry_delay(res.json() if res.content else {}),
                             "Gemini free-tier limit reached; waiting before trying again")
        if res.status_code in (401, 403):
            raise UserFacingError("The Gemini API key was rejected. Check GEMINI_API_KEY in .env.")
        if res.status_code == 404:
            raise UserFacingError(f"Gemini model '{self.model}' wasn't found. Run "
                                  "'npm run check-worker' to see which model names your key can use, "
                                  "then update GEMINI_MODEL in .env.")
        if res.status_code >= 500:
            raise RetryLater(60, f"Gemini is having trouble (error {res.status_code})")
        if res.status_code >= 400:
            raise RuntimeError(f"Gemini error {res.status_code}: {res.text[:300]}")

        body = res.json()
        meta = body.get("usageMetadata") or {}
        usage = LlmUsage(
            input_tokens=int(meta.get("promptTokenCount") or 0),
            # "thinking" tokens are billed as output
            output_tokens=int(meta.get("candidatesTokenCount") or 0) + int(meta.get("thoughtsTokenCount") or 0),
        )
        try:
            parts = body["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
            return parse_json(text), usage
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Gemini returned something we couldn't read: {str(body)[:300]}") from e

    def list_models(self) -> list[str]:
        res = self._http.get(f"{BASE}/models", headers={"x-goog-api-key": self.api_key},
                             params={"pageSize": 200})
        res.raise_for_status()
        return [m["name"].removeprefix("models/") for m in res.json().get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", [])]
