"""SkillOpt-style prompt optimizer: treat agent/instructions.md as trainable state.

Loop (rollout -> reflect -> gate): replay frozen research cases (evals/cases/)
through the production model with a candidate prompt, score each output with
the judge, have an optimizer model propose bounded edits from the train-set
verdicts, and accept an edit only if the mean score on held-out validation
cases improves. Every experiment — accepted or rejected — is appended to
evals/results/optimizer_log.jsonl, and every candidate prompt is versioned in
evals/prompt_history/.

Run:  python -m rigor.optimize [--experiments N] [--apply] [--max-usd X]

The live prompt is never modified unless --apply is passed; the winning prompt
always lands in evals/prompt_history/best.md.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import cases, config, governance, guardrails, judge, replay
from .llm import BudgetExceeded, UsageMeter, client
from .models import EditProposal, PromptEdit

PROMPT_PATH = config.INSTRUCTIONS_PATH
HISTORY_DIR = config.EVALS_DIR / "prompt_history"
LOG_PATH = config.EVALS_DIR / "results" / "optimizer_log.jsonl"

MAX_PROMPT_WORDS = int(config.config()["optimizer"]["max_prompt_words"])


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Pure edit application (unit-tested) ──


def apply_edits(prompt: str, edits: list[PromptEdit]) -> tuple[str | None, str]:
    """Apply bounded edits; return (new_prompt, "") or (None, reason) on failure."""
    if not 1 <= len(edits) <= 4:
        return None, f"proposal has {len(edits)} edits (must be 1-4)"
    text = prompt
    for e in edits:
        n = text.count(e.anchor)
        if n != 1:
            return None, f"anchor matches {n} times (must be exactly 1): {e.anchor[:60]!r}"
        if e.op == "replace":
            text = text.replace(e.anchor, e.text)
        elif e.op == "insert_after":
            text = text.replace(e.anchor, e.anchor + "\n" + e.text)
        elif e.op == "delete":
            text = text.replace(e.anchor, "")
        else:
            return None, f"unknown op: {e.op!r}"
    if not text.strip():
        return None, "edits produced an empty prompt"
    text = text.strip() + "\n"
    if len(text.split()) > MAX_PROMPT_WORDS:
        return None, f"prompt grew past {MAX_PROMPT_WORDS} words"
    return text, ""


# ── Rollout: replay one case with a candidate prompt, judge the result ──


def rollout(case: cases.ReplayCase, prompt_text: str, meter: UsageMeter,
            judge_samples: int) -> dict:
    briefing = replay.replay(case, prompt_text, meter)
    report = guardrails.check(briefing, verify=False)  # offline: no live link checks
    if report.must_block:
        return {"date": case.date, "score": 0.0, "blocked": True, "verdict": None}
    scores, verdict = [], None
    for _ in range(judge_samples):
        result = judge.judge(briefing, report.dead_links, meter)
        scores.append(result.weighted_total)
        verdict = verdict or result  # keep the first verdict's qualitative feedback
    return {"date": case.date, "score": round(statistics.mean(scores), 3),
            "blocked": False, "verdict": verdict}


def rollout_set(case_list: list[cases.ReplayCase], prompt_text: str, meter: UsageMeter,
                judge_samples: int, label: str) -> list[dict]:
    out = []
    for c in case_list:
        r = rollout(c, prompt_text, meter, judge_samples)
        print(f"    {label} {r['date']}: {r['score']}{' BLOCKED' if r['blocked'] else ''}",
              flush=True)
        out.append(r)
    return out


def mean_score(rollouts: list[dict]) -> float:
    return round(statistics.mean(r["score"] for r in rollouts), 3)


# ── Reflect: turn train verdicts into a bounded edit proposal ──


def _verdict_block(rollouts: list[dict]) -> str:
    chunks = []
    for r in rollouts:
        v = r["verdict"]
        if v is None:
            chunks.append(f"### CASE {r['date']}: BLOCKED by guardrails (score 0)")
            continue
        dims = "\n".join(f"- {d.dimension}: {d.score} — {d.rationale}" for d in v.dimensions)
        fixes = "\n".join(f"- {f}" for f in v.fixes) or "(none)"
        chunks.append(f"### CASE {r['date']} (weighted {r['score']})\n{dims}\nFIXES:\n{fixes}")
    return "\n\n".join(chunks)


def propose(prompt_text: str, train_rollouts: list[dict], history: list[dict],
            meter: UsageMeter) -> EditProposal:
    cfg = config.config()
    hist_lines = "\n".join(
        f"- exp {h['exp']} [{'ACCEPTED' if h['accepted'] else 'rejected'}, "
        f"val {h['val_mean']}]: {h['hypothesis']}"
        for h in history
    ) or "(first experiment this session)"
    user = (
        "CURRENT PROMPT:\n<<<PROMPT\n" + prompt_text + "\nPROMPT\n\n"
        "TRAIN ROLLOUT VERDICTS:\n" + _verdict_block(train_rollouts) + "\n\n"
        "EXPERIMENT HISTORY (this session):\n" + hist_lines + "\n\n"
        "Propose the next experiment."
    )
    model = cfg["models"]["optimizer"]
    resp = client().messages.parse(
        model=model,
        max_tokens=4000,
        system=config.read_prompt("optimizer.md"),
        output_format=EditProposal,
        output_config={"effort": cfg["effort"]["optimizer"]},
        messages=[{"role": "user", "content": user}],
    )
    meter.record(model, resp.usage)
    proposal = resp.parsed_output
    if proposal is None:
        raise RuntimeError(f"optimizer produced no proposal (stop={resp.stop_reason})")
    return proposal


# ── The training session ──


def _log(row: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(row) + "\n")


def _save_prompt(name: str, text: str) -> Path:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    path = HISTORY_DIR / name
    path.write_text(text)
    return path


def run(n_experiments: int, n_val: int, judge_samples: int, epsilon: float,
        max_usd: float, apply: bool) -> int:
    all_cases = cases.load_all()
    if len(all_cases) < 2:
        print(f"Need >= 2 replay cases in {cases.CASES_DIR} (found {len(all_cases)}).\n"
              "Cases are captured automatically by the deployed agent's daily runs —\n"
              "git pull to bring them down.", file=sys.stderr)
        return 1

    train, val = cases.split(all_cases, n_val)
    session = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    meter = UsageMeter(_budget={"max_usd_per_run": max_usd})

    manifest = governance.new_manifest("optimize")
    original = PROMPT_PATH.read_text()
    best = original
    _save_prompt(f"{session}-original.md", original)
    print(f"[{session}] cases: {len(train)} train / {len(val)} val "
          f"(val: {', '.join(c.date for c in val)}); budget ${max_usd:.2f}")

    history: list[dict] = []
    best_val = 0.0
    try:
        print("[baseline] rollouts…", flush=True)
        train_rollouts = rollout_set(train, best, meter, judge_samples, "train")
        val_rollouts = rollout_set(val, best, meter, judge_samples, "val")
        best_val = mean_score(val_rollouts)
        print(f"  baseline: train={mean_score(train_rollouts)} val={best_val}")
        _log({"ts": _utcnow(), "session": session, "exp": 0,
              "hypothesis": "(baseline)", "edits": [], "val_mean": best_val,
              "train_mean": mean_score(train_rollouts), "accepted": True,
              "reason": "baseline", "est_cost_usd": round(meter.est_cost_usd, 3)})

        for i in range(1, n_experiments + 1):
            print(f"[exp {i}/{n_experiments}] propose…", flush=True)
            proposal = propose(best, train_rollouts, history, meter)
            print(f"  hypothesis: {proposal.hypothesis}")
            candidate, err = apply_edits(best, proposal.edits)
            if candidate is None:
                print(f"  invalid proposal: {err}")
                _log({"ts": _utcnow(), "session": session,
                      "exp": i, "hypothesis": proposal.hypothesis,
                      "edits": [e.model_dump() for e in proposal.edits],
                      "val_mean": None, "accepted": False, "reason": f"invalid: {err}",
                      "est_cost_usd": round(meter.est_cost_usd, 3)})
                history.append({"exp": i, "hypothesis": proposal.hypothesis,
                                "accepted": False, "val_mean": "n/a (invalid edits)"})
                continue

            cand_rollouts = rollout_set(val, candidate, meter, judge_samples, "val")
            val_mean = mean_score(cand_rollouts)
            blocked = any(r["blocked"] for r in cand_rollouts)
            accepted = not blocked and val_mean >= best_val + epsilon
            verdict = ("ACCEPTED" if accepted else
                       "rejected (guardrails block)" if blocked else
                       f"rejected ({val_mean} < {round(best_val + epsilon, 3)})")
            print(f"  val={val_mean} vs best={best_val} -> {verdict}")

            _save_prompt(f"{session}-exp{i}-{'accepted' if accepted else 'rejected'}.md",
                         candidate)
            _log({"ts": _utcnow(), "session": session, "exp": i,
                  "hypothesis": proposal.hypothesis,
                  "edits": [e.model_dump() for e in proposal.edits],
                  "val_mean": val_mean, "best_val_before": best_val, "accepted": accepted,
                  "reason": verdict, "est_cost_usd": round(meter.est_cost_usd, 3)})
            history.append({"exp": i, "hypothesis": proposal.hypothesis,
                            "accepted": accepted, "val_mean": val_mean})

            if accepted:
                best, best_val = candidate, val_mean
                _save_prompt("best.md", best)
                # Refresh train feedback so the next proposal reflects the new prompt.
                print("  refresh train rollouts…", flush=True)
                train_rollouts = rollout_set(train, best, meter, judge_samples, "train")

    except BudgetExceeded as e:
        print(f"\nBUDGET EXHAUSTED: {e} — keeping best result so far.", file=sys.stderr)

    improved = best != original
    print(f"\nsession {session}: best val={best_val} "
          f"({'improved' if improved else 'no accepted edits'}), "
          f"est cost ${meter.est_cost_usd:.2f}")
    if improved:
        _save_prompt("best.md", best)
        if apply:
            PROMPT_PATH.write_text(best)
            print(f"APPLIED to {PROMPT_PATH.relative_to(config.ROOT)} — "
                  "commit + deploy to take effect in production")
        else:
            print(f"best prompt at {HISTORY_DIR.relative_to(config.ROOT)}/best.md — "
                  "re-run with --apply (or copy it) to deploy")

    manifest.input_tokens = meter.input_tokens
    manifest.output_tokens = meter.output_tokens
    manifest.est_cost_usd = round(meter.est_cost_usd, 4)
    manifest.status = "completed"
    manifest.notes = f"session {session}: best val={best_val}, applied={apply and improved}"
    governance.append_manifest(manifest)
    return 0


def main() -> int:
    opt = config.config()["optimizer"]
    p = argparse.ArgumentParser(description="Metric-gated prompt optimization loop")
    p.add_argument("--experiments", type=int, default=opt["experiments"])
    p.add_argument("--val", type=int, default=opt["val_cases"],
                   help="newest N cases held out for the validation gate")
    p.add_argument("--judge-samples", type=int, default=opt["judge_samples"],
                   help="judge each rollout N times and average (reduces judge noise)")
    p.add_argument("--epsilon", type=float, default=opt["epsilon"],
                   help="minimum val improvement to accept an edit")
    p.add_argument("--max-usd", type=float, default=opt["max_usd"],
                   help="hard cost ceiling for the whole session")
    p.add_argument("--apply", action="store_true",
                   help="write the winning prompt to agent/instructions.md")
    args = p.parse_args()
    return run(args.experiments, args.val, args.judge_samples, args.epsilon,
               args.max_usd, args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
