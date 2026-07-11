"""Output guardrails, run on a parsed briefing before judging.

Checks (from the agent's source-quality and final-QC rules):
- citation enforcement: every trend and watchlist card must cite >=1 source URL.
- link verification: every cited URL must resolve (catches hallucinated sources).
- content filters: blocked domains and down-rank noise keywords.
- prompt-injection scan on the model's own output.
- light PII scan.

A report separates `must_revise` issues (fixable by another synthesis pass) from
`must_block` issues (injection/PII — never publish)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from . import config
from .briefing import Briefing

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),
    re.compile(r"disregard\s+(the\s+)?(system|previous|above)", re.I),
    re.compile(r"you\s+are\s+now\s+", re.I),
    re.compile(r"system\s+prompt", re.I),
    re.compile(r"</?(system|instruction)s?>", re.I),
]
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


@dataclass
class GuardrailReport:
    dead_links: list[str] = field(default_factory=list)
    missing_citations: list[str] = field(default_factory=list)
    blocked_domain_hits: list[str] = field(default_factory=list)
    noise_hits: list[str] = field(default_factory=list)
    injection_hits: list[str] = field(default_factory=list)
    pii_hits: list[str] = field(default_factory=list)

    @property
    def must_revise(self) -> bool:
        return bool(
            self.dead_links or self.missing_citations or self.blocked_domain_hits or self.noise_hits
        )

    @property
    def must_block(self) -> bool:
        return bool(self.injection_hits or self.pii_hits)

    @property
    def ok(self) -> bool:
        return not (self.must_revise or self.must_block)

    def as_fixes(self) -> list[str]:
        fixes: list[str] = []
        for t in self.missing_citations:
            fixes.append(f"Add at least one real source link to: '{t}'.")
        for u in self.dead_links:
            fixes.append(f"Replace or remove the dead/unreachable source link: {u}")
        for h in self.blocked_domain_hits:
            fixes.append(f"Remove citation from blocked/low-quality domain: {h}")
        for h in self.noise_hits:
            fixes.append(f"Remove low-signal / off-topic noise item: {h}")
        return fixes


def _check_citations(b: Briefing, report: GuardrailReport) -> None:
    for c in b.cards:
        if c.kind in ("trend", "watch") and not c.urls:
            section = "Trend" if c.kind == "trend" else "Watchlist"
            report.missing_citations.append(f"{section}: {c.label}")


def _check_domains_and_noise(b: Briefing, report: GuardrailReport) -> None:
    src = config.sources()
    blocked = [d.lower() for d in src.get("blocked_domains", [])]
    keywords = [k.lower() for k in src.get("downrank_keywords", [])]
    for url in b.all_urls():
        host = (urlparse(url).hostname or "").lower()
        if any(host == d or host.endswith("." + d) for d in blocked):
            report.blocked_domain_hits.append(url)
    for c in b.cards:
        low = c.text.lower()
        for kw in keywords:
            if kw in low:
                report.noise_hits.append(f"{c.kind}:{c.label} contains '{kw}'")
                break


def _scan_injection_pii(b: Briefing, report: GuardrailReport) -> None:
    for pat in _INJECTION_PATTERNS:
        if pat.search(b.text):
            report.injection_hits.append(pat.pattern)
    if _EMAIL.search(b.text) or _SSN.search(b.text):
        report.pii_hits.append("email/SSN pattern in briefing text")


# Statuses that mean "the server responded but blocked our bot" — the resource
# almost certainly exists, so these are NOT treated as dead links.
_BOT_BLOCK_STATUSES = {401, 403, 405, 406, 429, 503, 999}
# Only these definitively mean the page is gone.
_DEAD_STATUSES = {404, 410}


def verify_links(urls: list[str], timeout: float = 8.0) -> list[str]:
    """Return only URLs that are definitively broken (404/410 or unreachable host).

    Best-effort. Bot-blocking responses (403/405/429/…) and transient 5xx are
    treated as reachable to avoid false positives that would wrongly force a
    revision — a real 404 or a DNS/connection failure is what we actually flag.
    """
    dead: list[str] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as c:
        for url in urls:
            verdict = None  # None until we get a definitive read
            for method in ("head", "get"):
                try:
                    resp = getattr(c, method)(url)
                except httpx.HTTPError:
                    verdict = "dead"          # DNS / connect / timeout / TLS error
                    continue                   # let GET retry override a HEAD failure
                sc = resp.status_code
                if sc < 400 or sc in _BOT_BLOCK_STATUSES:
                    verdict = "ok"
                    break
                if sc in _DEAD_STATUSES:
                    verdict = "dead"
                    break
                verdict = "dead"               # other 4xx/5xx — GET may still override
            if verdict == "dead":
                dead.append(url)
    return dead


def check(b: Briefing, verify: bool = True) -> GuardrailReport:
    report = GuardrailReport()
    _check_citations(b, report)
    _check_domains_and_noise(b, report)
    _scan_injection_pii(b, report)
    if verify:
        report.dead_links = verify_links(b.all_urls())
    return report
