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

# Property with well-formed define{} block: atomic props, all used in Assertion{}
_PROP_GOOD = """
property {
  define {
    cond = giveWayVessel.speed > 0;
    assure = giveWayVessel.actionTaken == 1;
  }
  Assertion {
    Rule22: !cond || assure;
  }
}
"""

# Property with a compound prop (cond && assure in RHS)
_PROP_COMPOUND = """
property {
  define {
    cond = giveWayVessel.speed > 0;
    assure = giveWayVessel.actionTaken == 1;
    combined = cond && assure;
  }
  Assertion {
    Rule22: !cond || assure || combined;
  }
}
"""

# Property where one defined prop is unused in Assertion{}
_PROP_UNUSED = """
property {
  define {
    cond = giveWayVessel.speed > 0;
    unused_prop = giveWayVessel.length > 50;
  }
  Assertion {
    Rule22: !cond;
  }
}
"""

_CM = {"assertion_lines": ["Rule22: !cond || assure;"]}


def test_logic_correctness_full() -> None:
    r = score_logic_correctness(_PROP_GOOD, _CM)
    assert r.score == 2
    assert r.detail["expression_complete"] == 1
    assert r.detail["semantic_correct"] == 1
    assert r.detail["expression_detail"]["unused"] == []
    assert r.detail["semantic_detail"]["compound_props"] == []


def test_logic_correctness_compound_prop() -> None:
    r = score_logic_correctness(_PROP_COMPOUND, _CM)
    assert r.detail["semantic_correct"] == 0
    assert "combined" in r.detail["semantic_detail"]["compound_props"]
    assert r.score == 1  # expression_complete=1, semantic=0


def test_logic_correctness_unused_prop() -> None:
    r = score_logic_correctness(_PROP_UNUSED, _CM)
    assert r.detail["expression_complete"] == 0
    assert "unused_prop" in r.detail["expression_detail"]["unused"]
    assert r.score <= 1


def test_logic_correctness_empty_property() -> None:
    r = score_logic_correctness("", {})
    assert r.detail["expression_complete"] == 0
    assert r.score == 0


def test_logic_correctness_no_assertion_block() -> None:
    prop = "property { define { cond = x.speed > 0; } }"
    r = score_logic_correctness(prop, {})
    assert r.detail["expression_complete"] == 0


def test_logic_correctness_verify_status_ignored() -> None:
    # verify_status and is_vacuous must not affect the score
    r_pass = score_logic_correctness(_PROP_GOOD, _CM, verify_status="pass", is_vacuous=False)
    r_fail = score_logic_correctness(_PROP_GOOD, _CM, verify_status="fail", is_vacuous=True)
    assert r_pass.score == r_fail.score == 2


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
    # rubric_total=7 (logic=0, no property_text); base=(7/9)*60=46.67+15+25=86.67 → 87
    assert card["score_total"] == 87


def test_scorer_normalization_vacuity_only() -> None:
    scorer = RubricScorer()
    card = scorer.score_rule(
        rule_id="Rule-22", verify_status="pass", rmc_exit_code=0, is_vacuous=False,
    )
    assert card["score_breakdown"]["mutation_pct"] is None
    # rubric_total=7 (logic=0, no property_text); base=(7/9)*85=66.11+15=81.11 → 81
    assert card["score_total"] == 81


def test_scorer_normalization_mutation_only() -> None:
    scorer = RubricScorer()
    card = scorer.score_rule(
        rule_id="Rule-22", verify_status="pass", rmc_exit_code=0, mutation_score=80.0,
    )
    assert card["score_breakdown"]["vacuity_pct"] is None
    # rubric_total=7 (logic=0, no property_text); base=(7/9)*75=58.33; mutation=0.8*25=20 → 78.33 → 78
    assert card["score_total"] == 78


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
