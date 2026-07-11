"""Load and parse the Eve agent's committed HTML briefings.

The agent emits `<body>` content using a fixed component vocabulary
(trend-card, contrarian-card, declining-card, watchlist-item — see
agent/instructions.md), so guardrails and the judge can work from the
committed HTML directly: per-card text + cited links, plus the whole
briefing's text and URL set.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from . import config

CARD_CLASSES = {
    "trend-card": "trend",
    "contrarian-card": "contrarian",
    "declining-card": "declining",
    "watchlist-item": "watch",
}
TITLE_CLASSES = {"trend-title", "watchlist-name"}

_FENCE_RE = re.compile(r"^```(?:html)?\s*|```\s*$", re.I)
_BODY_RE = re.compile(r"<body[^>]*>([\s\S]*?)</body>", re.I)


def extract_body(raw: str) -> str:
    """Mirror of the agent's extractBody: strip code fences / full-document wrappers."""
    s = _FENCE_RE.sub("", raw.strip()).strip()
    m = _BODY_RE.search(s)
    return m.group(1).strip() if m else s


@dataclass
class Card:
    kind: str            # trend | contrarian | declining | watch
    title: str = ""
    text: str = ""
    urls: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.title or "(untitled)"


class _BriefingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cards: list[Card] = []
        self.urls: list[str] = []
        self.text_parts: list[str] = []
        self._depth = 0
        self._card: Card | None = None
        self._card_depth = 0
        self._title_depth: int | None = None
        self._in_title_tag = 0  # h1-h3 inside a card, used when no title class exists

    @staticmethod
    def _classes(attrs) -> set[str]:
        for k, v in attrs:
            if k == "class" and v:
                return set(v.split())
        return set()

    def handle_starttag(self, tag, attrs):
        self._depth += 1
        classes = self._classes(attrs)
        if tag == "a":
            href = dict(attrs).get("href")
            if href and href.startswith(("http://", "https://")):
                self.urls.append(href)
                if self._card:
                    self._card.urls.append(href)
        if self._card:
            if (classes & TITLE_CLASSES) or (tag in ("h1", "h2", "h3") and not self._card.title):
                self._title_depth = self._depth
        else:
            hit = classes & CARD_CLASSES.keys()
            if hit:
                self._card = Card(kind=CARD_CLASSES[hit.pop()])
                self._card_depth = self._depth

    def handle_endtag(self, tag):
        if self._title_depth is not None and self._depth == self._title_depth:
            self._title_depth = None
        if self._card and self._depth == self._card_depth:
            self._card.text = self._card.text.strip()
            self._card.title = self._card.title.strip()
            self.cards.append(self._card)
            self._card = None
        self._depth -= 1

    def handle_data(self, data):
        if not data.strip():
            return
        self.text_parts.append(data)
        if self._card:
            self._card.text += data
            if self._title_depth is not None:
                self._card.title += data


@dataclass
class Briefing:
    date: str
    html: str
    cards: list[Card]
    text: str
    urls: list[str]

    def all_urls(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for u in self.urls:
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out


def from_html(date: str, raw_html: str) -> Briefing:
    body = extract_body(raw_html)
    p = _BriefingParser()
    p.feed(unescape(body) if "&lt;" in body[:200] else body)
    p.close()
    return Briefing(date=date, html=body, cards=p.cards,
                    text=" ".join(p.text_parts), urls=p.urls)


def path_for(date: str) -> Path:
    return config.BRIEFINGS_DIR / f"briefing-{date}.html"


def load(date: str) -> Briefing:
    return from_html(date, path_for(date).read_text())


def load_all() -> list[Briefing]:
    out = []
    for f in sorted(config.BRIEFINGS_DIR.glob("briefing-*.html")):
        date = f.stem.removeprefix("briefing-")
        out.append(from_html(date, f.read_text()))
    return out
