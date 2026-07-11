"""Pydantic schemas for the rigor layer: judge verdicts, optimizer proposals,
and the append-only audit manifest."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DimensionScore(BaseModel):
    dimension: str
    score: int = Field(description="1 (poor) to 5 (excellent).")
    rationale: str


class JudgeVerdict(BaseModel):
    """Raw output of the LLM-as-judge (scores + feedback; totals computed in code)."""

    dimensions: list[DimensionScore]
    fixes: list[str] = Field(description="Specific, actionable revisions for a failing briefing.")
    summary: str


class EvalResult(BaseModel):
    """Final scored record: judge verdict + code-computed totals/threshold."""

    dimensions: list[DimensionScore]
    fixes: list[str]
    summary: str
    weighted_total: float
    threshold: float
    passed: bool


class PromptEdit(BaseModel):
    """One bounded edit to the trainable prompt (SkillOpt-style add/delete/replace).

    `anchor` must match exactly one substring of the current prompt; an ambiguous
    or missing anchor invalidates the whole proposal (checked in code).
    """

    op: str = Field(description="One of: replace | insert_after | delete.")
    anchor: str = Field(description="Exact, unique substring of the current prompt to target.")
    text: str = Field(
        "", description="Replacement text (replace) or new text (insert_after). Empty for delete."
    )


class EditProposal(BaseModel):
    """Optimizer output: a hypothesis plus a small set of bounded prompt edits."""

    hypothesis: str = Field(
        description="One sentence: which rubric dimension(s) this should improve and why."
    )
    edits: list[PromptEdit] = Field(description="1-4 bounded edits. Fewer, sharper edits win.")


class RunManifest(BaseModel):
    """Append-only audit record, one per rigor run (logs/runs.jsonl)."""

    run_id: str
    kind: str  # eval | optimize
    timestamp: str
    models: dict[str, str]
    prompt_hashes: dict[str, str]
    input_tokens: int = 0
    output_tokens: int = 0
    est_cost_usd: float = 0.0
    briefings: dict[str, float] = Field(default_factory=dict)  # date -> weighted score
    all_passed: bool | None = None
    status: str = "started"  # started | completed | failed
    notes: str = ""
