"""Judge committed briefings against the rubric (governed regression eval).

    python -m rigor.eval                    # judge every briefing in briefings/
    python -m rigor.eval 2026-07-07         # judge one date
    python -m rigor.eval --last 3           # judge the newest N
    python -m rigor.eval --skip-verify      # offline (no live link checks)

Guardrails run first (citations, blocked domains, noise, injection/PII, dead
links), then the LLM judge scores each rubric dimension. Scores append to
evals/results/scores.jsonl and the run is recorded in the audit trail
(logs/runs.jsonl) with prompt/config hashes. Exit code is non-zero if any
briefing fails the rubric threshold or guardrails.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from . import briefing, config, governance, guardrails, judge
from .llm import UsageMeter

RESULTS = config.EVALS_DIR / "results" / "scores.jsonl"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dates", nargs="*", help="ISO dates to judge (default: all committed briefings)")
    ap.add_argument("--last", type=int, help="judge only the newest N briefings")
    ap.add_argument("--skip-verify", action="store_true", help="skip live link checks")
    args = ap.parse_args()

    if args.dates:
        briefings = [briefing.load(d) for d in args.dates]
    else:
        briefings = briefing.load_all()
        if args.last:
            briefings = briefings[-args.last:]
    if not briefings:
        print(f"No briefings found in {config.BRIEFINGS_DIR}", file=sys.stderr)
        return 1

    meter = UsageMeter()
    manifest = governance.new_manifest("eval")
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    all_passed = True
    try:
        for b in briefings:
            report = guardrails.check(b, verify=not args.skip_verify)
            result = judge.judge(b, report.dead_links, meter)
            ok = result.passed and report.ok
            all_passed = all_passed and ok
            manifest.briefings[b.date] = result.weighted_total
            print(f"\n{b.date}: total={result.weighted_total} pass={result.passed} "
                  f"guardrails_ok={report.ok} dead_links={len(report.dead_links)}")
            for d in result.dimensions:
                print(f"  {d.dimension:26s} {d.score}  — {d.rationale[:80]}")
            for fix in report.as_fixes():
                print(f"  guardrail: {fix}")
            with RESULTS.open("a") as out:
                out.write(json.dumps({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "date": b.date,
                    "weighted_total": result.weighted_total,
                    "passed": result.passed,
                    "guardrails_ok": report.ok,
                    "dead_links": report.dead_links,
                    "dimensions": {d.dimension: d.score for d in result.dimensions},
                    "fixes": result.fixes,
                    "run_id": manifest.run_id,
                }) + "\n")
        manifest.status = "completed"
    except Exception as e:
        manifest.status = "failed"
        manifest.notes = str(e)
        raise
    finally:
        manifest.input_tokens = meter.input_tokens
        manifest.output_tokens = meter.output_tokens
        manifest.est_cost_usd = round(meter.est_cost_usd, 4)
        manifest.all_passed = all_passed
        governance.append_manifest(manifest)

    print(f"\nest cost ${meter.est_cost_usd:.3f}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
