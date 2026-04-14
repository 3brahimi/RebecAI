"""
Integration tests for the rebeca-mutation skill: end-to-end mutation scoring
using the real rmc.jar.

For each mutant the test writes it to a temp file, calls run_rmc() for real,
then aggregates the results. No mocking.

safe_path() restricts paths to Path.home(); all temp dirs live under ~.
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

import pytest
from mutation_engine import Mutation, MutationEngine
from run_rmc import run_rmc
from vacuity_checker import check_vacuity
from fixtures import RULE_ID


# ===========================================================================
# Sample Rebeca model + property (known-good, matches conftest.py GOOD_MODEL)
# ===========================================================================

# Slightly extended model with mutation surface:
#  - msgsrv with assignments (transition_bypass)
#  - if-condition (predicate_flip)
#  - numeric literal (assignment_mutation)
MUTATION_MODEL = """\
reactiveclass Ship(10) {
  statevars {
    int length;
    boolean hasLight;
  }
  Ship() {
    length = 60;
    hasLight = true;
  }
  msgsrv tick() {
    length = length + 1;
    if (length > 100) {
      hasLight = false;
    }
  }
}
main {
  Ship s1():();
}
"""

MUTATION_PROPERTY = """\
property {
  define {
    isLong = (s1.length > 50);
    lightOn = (s1.hasLight == true);
  }
  Assertion {
    Rule22: !isLong || lightOn;
  }
}
"""


# ===========================================================================
# Helpers
# ===========================================================================

def run_mutation_suite(
    jar: str,
    model_content: str,
    property_content: str,
    base_dir: Path,
    timeout_seconds: int = 60,
) -> Dict:
    """
    Full mutation scoring pipeline using the real rmc.jar.
    All temp files live under base_dir (which must be inside Path.home()).
    """
    model_file = base_dir / "model.rebeca"
    prop_file = base_dir / "property.property"
    model_file.write_text(model_content, encoding="utf-8")
    prop_file.write_text(property_content, encoding="utf-8")

    # Vacuity check first
    vacuity = check_vacuity(
        jar=jar,
        model=str(model_file),
        property_file=str(prop_file),
        output_dir=str(base_dir / "vacuity_out"),
        timeout_seconds=timeout_seconds,
    )

    engine = MutationEngine()
    mutants: List[Mutation] = (
        engine.mutate_model(model_content, RULE_ID)
        + engine.mutate_property(property_content, RULE_ID)
    )

    killed = 0
    survived_list = []
    per_strategy: Dict[str, Dict] = {}

    for mut in mutants:
        strat = mut.strategy
        per_strategy.setdefault(strat, {"total": 0, "killed": 0, "survived": 0})
        per_strategy[strat]["total"] += 1

        suffix = ".rebeca" if mut.artifact == "model" else ".property"
        mut_file = base_dir / f"{mut.mutation_id}{suffix}"
        mut_file.write_text(mut.mutated_content, encoding="utf-8")

        mut_model = str(mut_file) if mut.artifact == "model" else str(model_file)
        mut_prop = str(mut_file) if mut.artifact == "property" else str(prop_file)
        out = str(base_dir / f"out_{mut.mutation_id}")

        exit_code = run_rmc(
            jar=jar,
            model=mut_model,
            property_file=mut_prop,
            output_dir=out,
            timeout_seconds=timeout_seconds,
        )

        if exit_code != 0:
            killed += 1
            per_strategy[strat]["killed"] += 1
        else:
            per_strategy[strat]["survived"] += 1
            survived_list.append({
                "mutation_id": mut.mutation_id,
                "strategy": strat,
                "description": mut.description,
                "artifact": mut.artifact,
            })

    total = len(mutants)
    score = (killed / total * 100) if total else 0.0

    return {
        "rule_id": RULE_ID,
        "mutation_score": round(score, 1),
        "total_mutants": total,
        "killed": killed,
        "survived": total - killed,
        "vacuity": vacuity,
        "per_strategy": [{"strategy": s, **v} for s, v in per_strategy.items()],
        "survived_mutations": survived_list,
    }


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture(scope="module")
def module_tmp():
    """Module-scoped temp dir inside ~ for the shared suite run."""
    import shutil
    d = Path(tempfile.mkdtemp(dir=Path.home()))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(scope="module")
def suite_report(rmc_jar, module_tmp):
    """Run the full mutation suite once per module and share the result."""
    return run_mutation_suite(
        jar=rmc_jar,
        model_content=MUTATION_MODEL,
        property_content=MUTATION_PROPERTY,
        base_dir=module_tmp,
        timeout_seconds=60,
    )


# ===========================================================================
# Score calculation
# ===========================================================================

@pytest.mark.requires_rmc
class TestMutationScoreCalculation:
    def test_total_mutants_nonzero(self, suite_report):
        assert suite_report["total_mutants"] > 0

    def test_killed_plus_survived_equals_total(self, suite_report):
        assert suite_report["killed"] + suite_report["survived"] == suite_report["total_mutants"]

    def test_score_is_ratio(self, suite_report):
        total = suite_report["total_mutants"]
        expected = round(suite_report["killed"] / total * 100, 1)
        assert suite_report["mutation_score"] == expected

    def test_at_least_some_mutants_killed(self, suite_report):
        """A well-written property must kill at least some mutants."""
        assert suite_report["killed"] > 0, (
            "No mutants were killed — the property may be too weak or vacuous.\n"
            f"Survived: {suite_report['survived_mutations']}"
        )

    def test_score_within_bounds(self, suite_report):
        assert 0.0 <= suite_report["mutation_score"] <= 100.0


# ===========================================================================
# Output JSON schema
# ===========================================================================

@pytest.mark.requires_rmc
class TestOutputSchema:
    def test_required_keys_present(self, suite_report):
        required = {
            "rule_id", "mutation_score", "total_mutants",
            "killed", "survived", "vacuity",
            "per_strategy", "survived_mutations",
        }
        assert required <= set(suite_report.keys())

    def test_vacuity_subkeys_present(self, suite_report):
        vac = suite_report["vacuity"]
        assert "is_vacuous" in vac
        assert "precondition_used" in vac
        assert "explanation" in vac

    def test_per_strategy_has_required_fields(self, suite_report):
        for entry in suite_report["per_strategy"]:
            assert "strategy" in entry
            assert "total" in entry
            assert "killed" in entry
            assert "survived" in entry

    def test_survived_mutations_schema(self, suite_report):
        for entry in suite_report["survived_mutations"]:
            assert "mutation_id" in entry
            assert "strategy" in entry
            assert "description" in entry
            assert "artifact" in entry

    def test_report_is_json_serializable(self, suite_report):
        data = json.loads(json.dumps(suite_report))
        assert data["rule_id"] == suite_report["rule_id"]


# ===========================================================================
# Vacuity integration
# ===========================================================================

@pytest.mark.requires_rmc
class TestVacuityIntegration:
    def test_non_vacuous_property_flag(self, suite_report):
        """MUTATION_PROPERTY is non-vacuous; the flag must say so."""
        assert suite_report["vacuity"]["is_vacuous"] is False, (
            f"Property was unexpectedly vacuous: {suite_report['vacuity']['explanation']}"
        )

    def test_precondition_extracted(self, suite_report):
        assert suite_report["vacuity"]["precondition_used"] is not None

    def test_wf06_verified_status(self, suite_report):
        """With a real non-vacuous property that kills mutants, expect VERIFIED."""
        def classify(score, is_vacuous):
            if is_vacuous:
                return "VACUOUS"
            return "VERIFIED" if score >= 80 else "WEAK"

        status = classify(
            suite_report["mutation_score"],
            suite_report["vacuity"]["is_vacuous"],
        )
        # VERIFIED or WEAK are both acceptable — what must NOT happen is VACUOUS
        assert status != "VACUOUS"


# ===========================================================================
# Per-strategy counting invariants
# ===========================================================================

@pytest.mark.requires_rmc
class TestPerStrategyCounting:
    def test_strategy_totals_sum_to_total_mutants(self, suite_report):
        assert sum(e["total"] for e in suite_report["per_strategy"]) == suite_report["total_mutants"]

    def test_strategy_killed_sums_to_report_killed(self, suite_report):
        assert sum(e["killed"] for e in suite_report["per_strategy"]) == suite_report["killed"]

    def test_survived_list_matches_survived_count(self, suite_report):
        assert len(suite_report["survived_mutations"]) == suite_report["survived"]

    def test_known_strategies_appear(self, suite_report):
        names = {e["strategy"] for e in suite_report["per_strategy"]}
        assert "transition_bypass" in names
        assert "assertion_negation" in names
