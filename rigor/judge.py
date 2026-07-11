"""LLM-as-judge: score a briefing against the rubric; compute pass/fail in code.

The model returns per-dimension scores (1-5) + rationale + specific fixes. The
weighted total and the pass/fail decision are computed deterministically here
from config/rubric.yaml so the governance decision doesn't depend on the model
doing arithmetic.
"""

from __future__ import annotations

from . import config
from .briefing import Briefing
from .llm import UsageMeter, client
from .models import EvalResult, JudgeVerdict

# Committed briefings are single-day and well under this; the cap only guards
# against a runaway replay blowing the judge's context.
MAX_BRIEFING_CHARS = 120_000


def _rubric_block() -> str:
    dims = config.rubric()["dimensions"]
    return "\n".join(f"- {d['name']} (weight {d['weight']}): {d['description'].strip()}" for d in dims)


def _score(verdict: JudgeVerdict) -> tuple[float, bool]:
    rub = config.rubric()
    weights = {d["name"].lower(): float(d["weight"]) for d in rub["dimensions"]}
    total_w = 0.0
    total_s = 0.0
    for d in verdict.dimensions:
        w = weights.get(d.dimension.lower(), 1.0)
        total_w += w
        total_s += w * d.score
    weighted = round(total_s / total_w, 3) if total_w else 0.0
    return weighted, weighted >= rub["pass_threshold"]


def judge(briefing: Briefing, dead_links: list[str], meter: UsageMeter) -> EvalResult:
    cfg = config.config()
    model = cfg["models"]["judge"]
    system = config.read_prompt("judge_rubric.md")

    dead_block = "\n".join(f"- {u}" for u in dead_links) or "(none reported)"
    user = (
        "RUBRIC DIMENSIONS:\n" + _rubric_block() + "\n\n"
        "DEAD / UNREACHABLE SOURCE LINKS (automated checker):\n" + dead_block + "\n\n"
        "BRIEFING (HTML body):\n" + briefing.html[:MAX_BRIEFING_CHARS] + "\n\n"
        "Score every rubric dimension by name, then give fixes and a summary."
    )

    resp = client().messages.parse(
        model=model,
        max_tokens=6000,
        system=system,
        output_format=JudgeVerdict,
        output_config={"effort": cfg["effort"]["judge"]},
        messages=[{"role": "user", "content": user}],
    )
    meter.record(model, resp.usage)
    verdict = resp.parsed_output
    if verdict is None:
        raise RuntimeError(f"judge produced no verdict (stop={resp.stop_reason})")

    weighted, passed = _score(verdict)
    return EvalResult(
        dimensions=verdict.dimensions,
        fixes=verdict.fixes,
        summary=verdict.summary,
        weighted_total=weighted,
        threshold=config.rubric()["pass_threshold"],
        passed=passed,
    )
