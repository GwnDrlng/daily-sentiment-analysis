"""Frozen replay cases for offline prompt optimization.

A case snapshots the research the Eve agent gathered on a given day — every
Tavily search (query + results) — so a candidate prompt can be replayed against
identical inputs and scored. The deployed agent captures a case automatically
with each briefing it archives (see agent/tools/save_briefing_to_repo.ts);
`git pull` brings them down into evals/cases/.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import config

CASES_DIR = config.EVALS_DIR / "cases"

# Per-result content is already capped at capture time; these caps bound the
# replay prompt if a day ran an unusually large number of searches.
MAX_RESULTS_PER_SEARCH = 8
MAX_CONTENT_CHARS = 1500


@dataclass
class SearchRecord:
    query: str
    results: list[dict] = field(default_factory=list)  # {title, url, content}


@dataclass
class ReplayCase:
    date: str                      # ISO date, also the case id
    searches: list[SearchRecord] = field(default_factory=list)

    def digest(self) -> str:
        """The frozen research notes, formatted as the replay model's evidence."""
        chunks = []
        for i, s in enumerate(self.searches, 1):
            lines = [f"## Search {i}: {s.query}"]
            for r in s.results[:MAX_RESULTS_PER_SEARCH]:
                content = (r.get("content") or "")[:MAX_CONTENT_CHARS]
                lines.append(f"### {r.get('title', '(untitled)')}\nURL: {r.get('url', '')}\n{content}")
            chunks.append("\n".join(lines))
        return "\n\n".join(chunks)


def load_all() -> list[ReplayCase]:
    """All replay cases, oldest first (filenames sort chronologically)."""
    cases = []
    for f in sorted(CASES_DIR.glob("case-*.json")):
        raw = json.loads(f.read_text())
        searches = [SearchRecord(query=s.get("query", ""), results=s.get("results", []))
                    for s in raw.get("searches", [])]
        cases.append(ReplayCase(date=raw["date"], searches=searches))
    return cases


def split(cases: list[ReplayCase], n_val: int) -> tuple[list[ReplayCase], list[ReplayCase]]:
    """Time-based split: the newest n_val cases are held out for validation."""
    n_val = max(1, min(n_val, len(cases) - 1))
    return cases[:-n_val], cases[-n_val:]
