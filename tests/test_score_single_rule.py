"""Unit tests for score_single_rule semantic signal integration."""

from __future__ import annotations

from skills.rebeca_tooling.scripts.score_single_rule import RubricScorer


def test_score_uses_rmc_modelout_mutation_and_vacuity_signals() -> None:
    scorer = RubricScorer()
    card = scorer.score_rule(
        rule_id="Rule-22",
        verify_status="pass",
        rmc_exit_code=0,
        model_outcome="satisfied",
        mutation_score=80.0,
        vacuity_comparison="same",
    )

    assert card["status"] == "Pass"
    assert card["score_breakdown"]["syntax"] == 10
    assert card["score_breakdown"]["semantic_alignment"] == 45  # 80*0.5 + 5
    assert card["score_breakdown"]["verification_outcome"] == 25
    assert card["score_breakdown"]["hallucination_penalty"] == 10
    assert card["score_total"] == 90


def test_model_out_cex_forces_fail_even_when_verify_status_pass() -> None:
    scorer = RubricScorer()
    card = scorer.score_rule(
        rule_id="Rule-22",
        verify_status="pass",
        rmc_exit_code=0,
        model_outcome="cex",
        mutation_score=100.0,
        vacuity_comparison="same",
    )

    assert card["status"] == "Fail"
    assert card["score_breakdown"]["verification_outcome"] == 0
    assert any("counterexample" in r for r in card["failure_reasons"])


def test_nonzero_rmc_exit_forces_fail() -> None:
    scorer = RubricScorer()
    card = scorer.score_rule(
        rule_id="Rule-22",
        verify_status="pass",
        rmc_exit_code=5,
        model_outcome="unknown",
        mutation_score=50.0,
        vacuity_comparison="changed",
    )

    assert card["status"] == "Fail"
    assert any("exit=5" in r for r in card["failure_reasons"])
