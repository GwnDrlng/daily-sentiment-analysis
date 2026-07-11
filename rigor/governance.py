"""Governance: prompt/version hashing and the append-only audit trail.

Every eval or optimization run appends a RunManifest to logs/runs.jsonl, with
hashes of the trainable prompt, the judge/optimizer prompts, and the versioned
config — so any score is traceable to the exact inputs that produced it.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from . import config
from .models import RunManifest

_RUNS_LOG = config.LOGS_DIR / "runs.jsonl"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def prompt_hashes() -> dict[str, str]:
    """Hash the prompts + versioned config so any score is traceable to its inputs."""
    hashes = {"agent/instructions.md": _sha(config.read_instructions())}
    for name in ("judge_rubric.md", "optimizer.md"):
        try:
            hashes[name] = _sha(config.read_prompt(name))
        except FileNotFoundError:
            hashes[name] = "missing"
    hashes["rigor.yaml"] = _sha(json.dumps(config.config(), sort_keys=True))
    hashes["rubric.yaml"] = _sha(json.dumps(config.rubric(), sort_keys=True))
    return hashes


def new_manifest(kind: str) -> RunManifest:
    cfg = config.config()
    return RunManifest(
        run_id="run_" + uuid.uuid4().hex[:10],
        kind=kind,
        timestamp=datetime.now(timezone.utc).isoformat(),
        models=cfg["models"],
        prompt_hashes=prompt_hashes(),
    )


def append_manifest(manifest: RunManifest) -> None:
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with _RUNS_LOG.open("a") as f:
        f.write(manifest.model_dump_json() + "\n")
