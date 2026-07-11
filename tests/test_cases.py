"""Replay-case loading and digest formatting (matches the JSON the deployed
agent commits via save_briefing_to_repo)."""

import json

from rigor import cases


def test_load_all_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(cases, "CASES_DIR", tmp_path)
    payload = {
        "date": "2026-07-10",
        "capturedAt": "2026-07-10T10:05:00Z",
        "searches": [
            {
                "query": "AI product management news",
                "results": [{"title": "T1", "url": "https://example.com/a", "content": "body"}],
                "at": "2026-07-10T10:01:00Z",
            }
        ],
    }
    (tmp_path / "case-2026-07-10.json").write_text(json.dumps(payload))
    loaded = cases.load_all()
    assert len(loaded) == 1
    case = loaded[0]
    assert case.date == "2026-07-10"
    assert case.searches[0].query == "AI product management news"
    digest = case.digest()
    assert "AI product management news" in digest
    assert "https://example.com/a" in digest


def test_digest_caps_results_and_content(tmp_path, monkeypatch):
    monkeypatch.setattr(cases, "CASES_DIR", tmp_path)
    results = [{"title": f"T{i}", "url": f"https://example.com/{i}", "content": "x" * 5000}
               for i in range(20)]
    case = cases.ReplayCase(date="2026-07-10",
                            searches=[cases.SearchRecord(query="q", results=results)])
    digest = case.digest()
    assert digest.count("### T") == cases.MAX_RESULTS_PER_SEARCH
    assert "x" * (cases.MAX_CONTENT_CHARS + 1) not in digest
