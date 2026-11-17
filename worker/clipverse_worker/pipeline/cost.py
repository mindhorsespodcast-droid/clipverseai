"""Running cost log for one job (brief rule 8: know our cost per minute of video)."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .. import pricing


@dataclass
class Cost:
    stt_audio_seconds: float = 0.0
    stt_usd: float = 0.0
    llm_input_tokens: int = 0
    llm_output_tokens: int = 0
    llm_usd: float = 0.0
    stt_model: str = ""
    llm_model: str = ""

    @staticmethod
    def from_job(job: dict) -> "Cost":
        known = Cost.__dataclass_fields__
        return Cost(**{k: v for k, v in (job.get("cost_breakdown") or {}).items() if k in known})

    def add_stt(self, model: str, seconds: float) -> None:
        self.stt_model = model
        self.stt_audio_seconds += seconds
        self.stt_usd += pricing.stt_cost(model, seconds)

    def add_llm(self, model: str, usage) -> None:
        self.llm_model = model
        self.llm_input_tokens += usage.input_tokens
        self.llm_output_tokens += usage.output_tokens
        self.llm_usd += pricing.llm_cost(model, usage.input_tokens, usage.output_tokens)

    @property
    def total_usd(self) -> float:
        return self.stt_usd + self.llm_usd

    def as_dict(self) -> dict:
        d = asdict(self)
        d["stt_usd"] = round(d["stt_usd"], 6)
        d["llm_usd"] = round(d["llm_usd"], 6)
        return d
