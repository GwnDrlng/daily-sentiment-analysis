"""LLM clients + usage/cost accounting.

Two backends:
- Anthropic (judge, optimizer) — structured outputs via `messages.parse`.
- Ollama Cloud's OpenAI-compatible endpoint (replay generator) — the same
  GLM model the deployed Eve agent uses, called over plain httpx.

Every call goes through one `UsageMeter` so token usage and estimated spend
accumulate into the audit manifest and the per-run budget guardrail.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import anthropic
import httpx
from dotenv import load_dotenv

from . import config

# Same precedence as the Eve agent: .env.local holds local secrets.
load_dotenv(config.ROOT / ".env.local")
load_dotenv(config.ROOT / ".env")

_client: anthropic.Anthropic | None = None

OLLAMA_BASE_URL = "https://ollama.com/v1"


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # resolves ANTHROPIC_API_KEY from env
    return _client


class BudgetExceeded(RuntimeError):
    """Raised when a run exceeds its cost ceiling."""


@dataclass
class UsageMeter:
    input_tokens: int = 0
    output_tokens: int = 0
    est_cost_usd: float = 0.0
    _pricing: dict = field(default_factory=lambda: config.config()["pricing"])
    _budget: dict = field(default_factory=lambda: config.config()["budget"])

    def record(self, model: str, usage) -> None:
        it = getattr(usage, "input_tokens", 0) or 0
        ot = getattr(usage, "output_tokens", 0) or 0
        self.input_tokens += it
        self.output_tokens += ot
        price = self._pricing.get(model)
        if price:
            self.est_cost_usd += (it / 1e6) * price["input"] + (ot / 1e6) * price["output"]
        self._enforce()

    def record_counts(self, model: str, input_tokens: int, output_tokens: int) -> None:
        class _U:
            pass

        u = _U()
        u.input_tokens = input_tokens
        u.output_tokens = output_tokens
        self.record(model, u)

    def _enforce(self) -> None:
        if self.est_cost_usd > self._budget["max_usd_per_run"]:
            raise BudgetExceeded(
                f"cost ${self.est_cost_usd:.2f} exceeds cap ${self._budget['max_usd_per_run']}"
            )


def ollama_chat(model: str, system: str, user: str, meter: UsageMeter,
                max_tokens: int = 16000, timeout: float = 600.0) -> str:
    """One chat completion against Ollama Cloud (OpenAI-compatible)."""
    api_key = os.environ.get("OLLAMA_API_KEY")
    if not api_key:
        raise RuntimeError("OLLAMA_API_KEY is not set (needed for replay rollouts)")
    resp = httpx.post(
        f"{OLLAMA_BASE_URL}/chat/completions",
        timeout=timeout,
        headers={"authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
    )
    resp.raise_for_status()
    data = resp.json()
    usage = data.get("usage") or {}
    meter.record_counts(model, usage.get("prompt_tokens", 0) or 0,
                        usage.get("completion_tokens", 0) or 0)
    return data["choices"][0]["message"]["content"] or ""
