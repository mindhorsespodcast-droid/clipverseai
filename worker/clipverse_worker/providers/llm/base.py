"""LLM plug: send instructions, get JSON back. Used for picking moments and caption scripts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class LlmUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, other: "LlmUsage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens


class Llm(Protocol):
    name: str
    model: str

    def complete_json(self, task: str, system: str, prompt: str) -> tuple[Any, LlmUsage]:
        """Return parsed JSON. `task` is a short label ("moments", "scripts") for logs/tests."""
