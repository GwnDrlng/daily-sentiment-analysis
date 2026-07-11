"""Offline tests for the prompt-optimization loop's pure pieces:
bounded edit application and the train/val case split."""

from rigor import cases
from rigor.models import PromptEdit
from rigor.optimize import MAX_PROMPT_WORDS, apply_edits

PROMPT = "# STYLE\nBe concise.\n\n# SOURCES\nPrefer primary sources.\n"


def test_replace():
    out, err = apply_edits(PROMPT, [PromptEdit(op="replace", anchor="Be concise.",
                                               text="Be terse.")])
    assert err == ""
    assert "Be terse." in out and "Be concise." not in out


def test_insert_after():
    out, err = apply_edits(PROMPT, [PromptEdit(op="insert_after", anchor="# STYLE",
                                               text="No hedging.")])
    assert err == ""
    assert "# STYLE\nNo hedging.\nBe concise." in out


def test_delete():
    out, err = apply_edits(PROMPT, [PromptEdit(op="delete", anchor="Prefer primary sources.")])
    assert err == ""
    assert "Prefer primary sources." not in out


def test_missing_anchor_rejected():
    out, err = apply_edits(PROMPT, [PromptEdit(op="replace", anchor="nonexistent", text="x")])
    assert out is None and "matches 0 times" in err


def test_ambiguous_anchor_rejected():
    out, err = apply_edits("a b a", [PromptEdit(op="delete", anchor="a")])
    assert out is None and "matches 2 times" in err


def test_unknown_op_rejected():
    out, err = apply_edits(PROMPT, [PromptEdit(op="prepend", anchor="# STYLE", text="x")])
    assert out is None and "unknown op" in err


def test_too_many_edits_rejected():
    edits = [PromptEdit(op="delete", anchor=f"x{i}") for i in range(5)]
    out, err = apply_edits(PROMPT, edits)
    assert out is None and "must be 1-4" in err


def test_empty_result_rejected():
    out, err = apply_edits("only line", [PromptEdit(op="delete", anchor="only line")])
    assert out is None and "empty" in err


def test_word_cap_enforced():
    big = " ".join(["word"] * (MAX_PROMPT_WORDS + 1))
    out, err = apply_edits(PROMPT, [PromptEdit(op="insert_after", anchor="# STYLE", text=big)])
    assert out is None and "grew past" in err


def test_live_prompt_fits_under_cap():
    from rigor import config
    assert len(config.read_instructions().split()) <= MAX_PROMPT_WORDS


def _case(date: str) -> cases.ReplayCase:
    return cases.ReplayCase(date=date, searches=[])


def test_split_holds_out_newest():
    cs = [_case(f"2026-07-0{i}") for i in range(1, 6)]
    train, val = cases.split(cs, 2)
    assert [c.date for c in val] == ["2026-07-04", "2026-07-05"]
    assert len(train) == 3


def test_split_always_keeps_a_train_case():
    cs = [_case("2026-07-01"), _case("2026-07-02")]
    train, val = cases.split(cs, 5)
    assert len(train) == 1 and len(val) == 1
