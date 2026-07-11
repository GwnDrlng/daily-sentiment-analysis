"""Load versioned YAML config and resolve project paths.

The rigor layer lives beside the Eve agent: it reads the agent's committed
briefings (briefings/), trains the agent's system prompt
(agent/instructions.md), and keeps its own state under evals/ and logs/.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml

# repo root = one level up from this file (rigor/config.py -> repo)
ROOT = Path(__file__).resolve().parents[1]

CONFIG_DIR = ROOT / "config"
PROMPTS_DIR = ROOT / "rigor" / "prompts"
BRIEFINGS_DIR = ROOT / "briefings"
EVALS_DIR = ROOT / "evals"
LOGS_DIR = ROOT / "logs"

# The Eve agent's system prompt — the trainable state of the optimization loop.
INSTRUCTIONS_PATH = ROOT / "agent" / "instructions.md"


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return yaml.safe_load(f)


@functools.lru_cache(maxsize=None)
def config() -> dict[str, Any]:
    return _load_yaml(CONFIG_DIR / "rigor.yaml")


@functools.lru_cache(maxsize=None)
def sources() -> dict[str, Any]:
    return _load_yaml(CONFIG_DIR / "sources.yaml")


@functools.lru_cache(maxsize=None)
def rubric() -> dict[str, Any]:
    return _load_yaml(CONFIG_DIR / "rubric.yaml")


def read_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text()


def read_instructions() -> str:
    return INSTRUCTIONS_PATH.read_text()
