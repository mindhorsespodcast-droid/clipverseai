"""Groq-hosted open models (OpenAI-style chat API), free tier. Used as a backup when Gemini's
free-tier limit is reached. Docs: console.groq.com/docs/text-chat"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from ...errors import RetryLater, UserFacingError
from .base import LlmUsage
from .gemini import parse_json

BASE = "https://api.groq.com/openai/v1"


class GroqLlm:
    name = "groq"

    def __init__(self, api_key: str, model: str, client: httpx.Client | None = None):
        self.api_key = api_key
        self.model = model
        self._http = client or httpx.Client(timeout=180)

    def _post(self, model: str, system: str, prompt: str) -> httpx.Response:
        return self._http.post(
            f"{BASE}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.4,
            },
        )

    def complete_json(self, task: str, system: str, prompt: str) -> tuple[Any, LlmUsage]:
        try:
            res = self._post(self.model, system, prompt)
        except httpx.HTTPError as e:
            raise RetryLater(60, f"Couldn't reach Groq ({e.__class__.__name__})") from e
        if res.status_code == 429:
            raise RetryLater(float(res.headers.get("retry-after", "60") or 60),
                             "Groq free-tier limit reached; waiting before trying again")
        if res.status_code in (401, 403):
            raise UserFacingError("The Groq API key was rejected. Check GROQ_API_KEY in .env.")
        if res.status_code == 404:
            raise UserFacingError(f"Groq model '{self.model}' wasn't found. Run 'npm run check-worker' "
                                  "to see which model to put in GROQ_LLM_MODEL in .env.")
        if res.status_code >= 500:
            raise RetryLater(60, f"Groq is having trouble (error {res.status_code})")
        if res.status_code >= 400:
            raise RuntimeError(f"Groq error {res.status_code}: {res.text[:300]}")
        body = res.json()
        u = body.get("usage") or {}
        usage = LlmUsage(int(u.get("prompt_tokens") or 0), int(u.get("completion_tokens") or 0))
        try:
            return parse_json(body["choices"][0]["message"]["content"] or ""), usage
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Groq returned something we couldn't read: {str(body)[:300]}") from e

    def works(self, model: str) -> tuple[bool, str]:
        try:
            res = self._post(model, "Answer in JSON.", 'Reply with {"ok": true}')
        except httpx.HTTPError as e:
            return False, e.__class__.__name__
        return res.status_code in (200, 429), f"error {res.status_code}"

    def list_models(self) -> list[str]:
        res = self._http.get(f"{BASE}/models", headers={"Authorization": f"Bearer {self.api_key}"})
        res.raise_for_status()
        return [m["id"] for m in res.json().get("data", [])]

    @staticmethod
    def rank_candidates(models: list[str]) -> list[str]:
        skip = ("whisper", "guard", "tts", "playai", "orpheus", "distil", "embed", "safeguard", "compound")
        usable = [m for m in models if not any(x in m.lower() for x in skip)]

        def key(m: str):
            big = max([int(n) for n in re.findall(r"(\d+)b", m.lower())] or [0])
            return (-big, m)

        return sorted(usable, key=key)


class FallbackLlm:
    """Use the main AI; if it hits a free-tier limit with a long wait, use the backup instead."""

    def __init__(self, primary, backup, max_wait: float = 90):
        self.primary, self.backup, self.max_wait = primary, backup, max_wait
        self.name = f"{primary.name}+{backup.name}"
        self.model = primary.model

    def complete_json(self, task: str, system: str, prompt: str):
        try:
            self.model = self.primary.model
            return self.primary.complete_json(task, system, prompt)
        except RetryLater as e:
            if e.seconds <= self.max_wait and "limit" not in e.reason.lower():
                raise
            import logging
            logging.getLogger("worker").warning("%s: %s - using backup %s (%s)", self.primary.name, e.reason,
                                                self.backup.name, self.backup.model)
            self.model = self.backup.model
            return self.backup.complete_json(task, system, prompt)
