"""Unit tests for score_rule TQC 9-point rubric and normalization."""

from __future__ import annotations

import pytest
from skills.rebeca_tooling.scripts.score_rule import (
    RubricScorer,
    score_syntax_correctness,
    score_attribute_coverage,
    score_actor_coverage,
    score_hallucination_free,
    score_logic_correctness,
)


# ---------------------------------------------------------------------------
# Helper 1 — Syntax correctness
# ---------------------------------------------------------------------------

def test_syntax_pass_exit_zero() -> None:
    r = score_syntax_correctness(0)
    assert r.score == 1
    assert r.detail["stage_failed"] is None


def test_syntax_fail_rmc_parse() -> None:
    stderr = "line:5, column:3, no viable alternative at input 'foo'"
    r = score_syntax_correctness(5, rmc_stderr_content=stderr)
    assert r.score == 0
    assert r.detail["stage_failed"] == "rmc_parse"
    assert len(r.detail["error_lines"]) == 1


def test_syntax_fail_cpp_compile() -> None:
    stderr = "model.cpp:10:5: error: 'x' was not declared in this scope"
    r = score_syntax_correctness(4, compile_stderr_content=stderr)
    assert r.score == 0
    assert r.detail["stage_failed"] == "cpp_compile"


def test_syntax_fail_timeout() -> None:
    r = score_syntax_correctness(3)
    assert r.score == 0
    assert r.detail["stage_failed"] == "rmc_timeout"


# ---------------------------------------------------------------------------
# Helper 2 — Attribute coverage
# ---------------------------------------------------------------------------

def test_attribute_coverage_full() -> None:
    vm = {"speed": {}, "length": {}}
    cm = {
        "statevar_patches": [{"reactiveclass": "Ship", "add_statevars": [
            {"name": "speed", "type": "int", "default": "0"},
            {"name": "length", "type": "int", "default": "0"},
        ]}],
        "define_patches": [],
    }
    r = score_attribute_coverage(vm, cm)
    assert r.score == 3
    assert r.detail["coverage_pct"] == 100.0


def test_attribute_coverage_partial() -> None:
    vm = {"speed": {}, "length": {}, "visibility": {}}
    cm = {
        "statevar_patches": [{"reactiveclass": "Ship", "add_statevars": [
            {"name": "speed", "type": "int", "default": "0"},
        ]}],
        "define_patches": [],
    }
    r = score_attribute_coverage(vm, cm)
    # 1/3 = 33.3% → score 1
    assert r.score == 1


def test_attribute_coverage_via_define_expr() -> None:
    vm = {"shipLength": {}}
    cm = {
        "statevar_patches": [],
        "define_patches": [{"alias": "LongShip", "expr": "giveWayVessel.shipLength >= 50"}],
    }
    r = score_attribute_coverage(vm, cm)
    assert r.score == 3


def test_attribute_coverage_empty_required() -> None:
    r = score_attribute_coverage({}, {})
    assert r.score == 3  # nothing required → full coverage


# ---------------------------------------------------------------------------
# Helper 3 — Actor coverage
# ---------------------------------------------------------------------------

def test_actor_coverage_all() -> None:
    am = {"GiveWayVessel": {}, "StandOnVessel": {}}
    cm = {
        "statevar_patches": [
            {"reactiveclass": "GiveWayVessel", "add_statevars": []},
            {"reactiveclass": "StandOnVessel", "add_statevars": []},
        ],
        "queue_size_patches": [],
    }
    r = score_actor_coverage(am, cm)
    assert r.score == 2


def test_actor_coverage_some() -> None:
    am = {"GiveWayVessel": {}, "StandOnVessel": {}}
    cm = {
        "statevar_patches": [{"reactiveclass": "GiveWayVessel", "add_statevars": []}],
        "queue_size_patches": [],
    }
    r = score_actor_coverage(am, cm)
    assert r.score == 1


def test_actor_coverage_none() -> None:
    am = {"GiveWayVessel": {}}
    cm = {"statevar_patches": [], "queue_size_patches": []}
    r = score_actor_coverage(am, cm)
    assert r.score == 0


# ---------------------------------------------------------------------------
# Helper 4 — No hallucinations
# ---------------------------------------------------------------------------

def test_hallucination_clean_pass() -> None:
    r = score_hallucination_free(0)
    assert r.score == 1
    assert r.detail["stage"] == "clean"


def test_hallucination_rmc_undefined() -> None:
    r = score_hallucination_free(5, rmc_stderr_content="undefined symbol 'fooBar'")
    assert r.score == 0
    assert r.detail["stage"] == "rmc_parse"


def test_hallucination_cpp_no_member() -> None:
    r = score_hallucination_free(4, compile_stderr_content="'Ship' has no member named 'ghost'")
    assert r.score == 0
    assert r.detail["stage"] == "cpp_compile"


def test_hallucination_syntax_only_not_flagged_as_hallucination() -> None:
    stderr = "line:5, column:3, no viable alternative at input 'if'"
    r = score_hallucination_free(5, rmc_stderr_content=stderr)
    assert r.score == 0
    assert r.detail["stage"] == "syntax_or_other_error"
    assert r.detail["matched_patterns"] == []


# ---------------------------------------------------------------------------
# Helper 5 — Logic correctness
# ---------------------------------------------------------------------------

_PROP = """
define Rule22_cond := giveWayVessel.speed > 0;
define Rule22_assure := giveWayVessel.actionTaken;
assertion Rule22: !Rule22_cond || Rule22_assure;
"""

_CM = {"assertion_lines": ["Rule22: !Rule22_cond || Rule22_assure;"]}


def test_logic_correctness_full() -> None:
    r = score_logic_correctness(_PROP, _CM, "pass", False)
    assert r.score == 2
    assert r.detail["expression_complete"] == 1
    assert r.detail["semantic_correct"] == 1


def test_logic_correctness_fail_verification() -> None:
    r = score_logic_correctness(_PROP, _CM, "fail", None)
    assert r.detail["semantic_correct"] == 0
    assert r.score == 1  # expression_complete=1, semantic=0


def test_logic_correctness_vacuous_pass() -> None:
    r = score_logic_correctness(_PROP, _CM, "pass", True)
    assert r.detail["semantic_correct"] == 0  # vacuous → 0
    assert r.score == 1


def test_logic_correctness_missing_assertion() -> None:
    r = score_logic_correctness("", {}, "pass", False)
    assert r.detail["expression_complete"] == 0


# ---------------------------------------------------------------------------
# RubricScorer integration
# ---------------------------------------------------------------------------

def test_scorer_pass_no_optional() -> None:
    scorer = RubricScorer()
    card = scorer.score_rule(rule_id="Rule-22", verify_status="pass", rmc_exit_code=0)
    assert card["status"] == "Pass"
    assert card["rubric_9pt"]["total"] == card["rubric_9pt"]["syntax_correctness"]["score"] + \
           card["rubric_9pt"]["attribute_coverage"]["score"] + \
           card["rubric_9pt"]["actor_coverage"]["score"] + \
           card["rubric_9pt"]["hallucination_free"]["score"] + \
           card["rubric_9pt"]["logic_correctness"]["score"]
    assert card["score_breakdown"]["vacuity_pct"] is None
    assert card["score_breakdown"]["mutation_pct"] is None


def test_scorer_normalization_both_enabled() -> None:
    scorer = RubricScorer()
    card = scorer.score_rule(
        rule_id="Rule-22",
        verify_status="pass",
        rmc_exit_code=0,
        is_vacuous=False,
        mutation_score=100.0,
    )
    assert card["score_breakdown"]["vacuity_pct"] == 15.0
    assert card["score_breakdown"]["mutation_pct"] == 25.0
    # rubric_total=8 (expression_complete=0, no property_text); base=(8/9)*60=53.33+15+25=93
    assert card["score_total"] == 93


def test_scorer_normalization_vacuity_only() -> None:
    scorer = RubricScorer()
    card = scorer.score_rule(
        rule_id="Rule-22", verify_status="pass", rmc_exit_code=0, is_vacuous=False,
    )
    assert card["score_breakdown"]["mutation_pct"] is None
    # rubric_total=8; base=(8/9)*85=75.56+15=90.56 → 91
    assert card["score_total"] == 91


def test_scorer_normalization_mutation_only() -> None:
    scorer = RubricScorer()
    card = scorer.score_rule(
        rule_id="Rule-22", verify_status="pass", rmc_exit_code=0, mutation_score=80.0,
    )
    assert card["score_breakdown"]["vacuity_pct"] is None
    # rubric_total=8; base=(8/9)*75=66.67; mutation=0.8*25=20 → 86.67 → 87
    assert card["score_total"] == 87


def test_scorer_cex_forces_fail() -> None:
    scorer = RubricScorer()
    card = scorer.score_rule(
        rule_id="Rule-22", verify_status="pass", rmc_exit_code=0, model_outcome="cex"
    )
    assert card["status"] == "Fail"
    assert any("counterexample" in r for r in card["failure_reasons"])


def test_scorer_nonzero_exit_forces_fail() -> None:
    scorer = RubricScorer()
    card = scorer.score_rule(rule_id="Rule-22", verify_status="pass", rmc_exit_code=5)
    assert card["status"] == "Fail"
    assert any("exit=5" in r for r in card["failure_reasons"])


def test_scorer_rubric_9pt_schema_always_present() -> None:
    scorer = RubricScorer()
    for status in ("pass", "fail", "timeout", "blocked", "unknown"):
        card = scorer.score_rule(rule_id="Rule-X", verify_status=status)
        assert "rubric_9pt" in card
        r = card["rubric_9pt"]
        for key in ("syntax_correctness", "attribute_coverage", "actor_coverage",
                    "hallucination_free", "logic_correctness", "total", "max"):
            assert key in r, f"missing key '{key}' for status={status}"
