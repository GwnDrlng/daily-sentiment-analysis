"""Replay: regenerate a briefing from a frozen research case with a candidate
prompt, on the SAME model the deployed agent uses (GLM via Ollama Cloud).

This substitutes for the agent's live run: instead of the model calling
web_search, it receives the day's frozen search results as evidence and writes
the <body> HTML per its instructions. Strictly offline — no web access exists
on this path, so replay can never invent fresh research.
"""

from __future__ import annotations

from datetime import date as _date

from . import briefing, config
from .cases import ReplayCase
from .llm import UsageMeter, ollama_chat

_REPLAY_DIRECTIVE = (
    "\n\n## REPLAY MODE\n"
    "The day's web research has already been gathered and is provided below as "
    "RESEARCH NOTES — you have no search tool. Use ONLY the sources in the notes; "
    "never invent a URL. Write the full briefing now as <body> HTML per the "
    "OUTPUT FORMAT (component classes and badge levels). Output ONLY the HTML — "
    "no code fences, no commentary."
)


def _weekday_display(date_iso: str) -> str:
    d = _date.fromisoformat(date_iso)
    return d.strftime("%A, %B %-d, %Y")


def replay(case: ReplayCase, instructions_text: str, meter: UsageMeter) -> briefing.Briefing:
    model = config.config()["models"]["generator"]
    user = (
        f"Produce the Daily PM & AI Strategic Intelligence Briefing for "
        f"{_weekday_display(case.date)} ({case.date}).\n\n"
        "RESEARCH NOTES (frozen from that day's run):\n\n" + case.digest()
    )
    html = ollama_chat(model, instructions_text + _REPLAY_DIRECTIVE, user, meter)
    return briefing.from_html(case.date, html)
