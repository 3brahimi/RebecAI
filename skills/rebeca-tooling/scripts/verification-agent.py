#!/usr/bin/env python3
"""
verification-agent (WF-05): RMC Verification, Vacuity Check, Mutation Scoring

Orchestrates:
  1. run_rmc      — compile .rebeca + .property → exit code classification
  2. check_vacuity — vacuity check (only when rmc_exit_code == 0)
  3. MutationEngine — mutation scoring (only when rmc_exit_code == 0)

Exit codes:
  0: Success — full contract written to stdout
  1: Failure — error envelope written to stdout
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Bootstrap: add skills scripts to sys.path
# ---------------------------------------------------------------------------
_SCRIPTS = Path(__file__).parent.parent / "skills" / "rebeca-tooling" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from run_rmc import run_rmc                          # noqa: E402
from vacuity_checker import check_vacuity            # noqa: E402
from mutation_engine import MutationEngine           # noqa: E402
from utils import safe_path                          # noqa: E402


# ---------------------------------------------------------------------------
# RMC exit code → outcome label
# ---------------------------------------------------------------------------
_RMC_OUTCOME: Dict[int, str] = {
    0: "verified",
    1: "invalid_inputs",
    3: "timeout",
    4: "cpp_compile_failed",
    5: "parse_failed",
}

_OPEN_ASSUMPTIONS = [
    "NOTE: run_rmc only compiles the model to C++ — mutation_score reflects "
    "syntactic (compile-time) kills only, not semantic or runtime kills.",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(message: str) -> Dict[str, Any]:
    """Canonical Error Envelope for WF-05."""
    return {
        "status":  "error",
        "phase":   "step05",
        "agent":   "verification-agent",
        "message": message,
    }


def _checked_safe_path(p: str, label: str) -> Tuple[Optional[Path], Optional[str]]:
    """Wrap safe_path() to catch its sys.exit and return an error string instead."""
    try:
        return safe_path(p), None
    except SystemExit:
        return None, f"{label} path escapes allowed base (~): {p}"
    except Exception as exc:
        return None, f"{label} path error: {exc}"


def _validate_output(result: Dict[str, Any]) -> Optional[str]:
    """
    Validate result against the output sub-schema.
    Returns an error string on violation, None if valid or jsonschema unavailable.
    """
    schema_path = Path(__file__).parent / "verification-agent.schema.json"
    try:
        import jsonschema  # type: ignore
        if not schema_path.exists():
            return None
        root_schema = json.loads(schema_path.read_text(encoding="utf-8"))
        output_schema = root_schema.get("output")
        if output_schema:
            combined = {
                "definitions": root_schema.get("definitions", {}),
                **output_schema,
            }
            errors = list(jsonschema.Draft7Validator(combined).iter_errors(result))
            if errors:
                return f"Output schema validation failed: {errors[0].message}"
    except ImportError:
        pass
    except Exception as exc:
        return f"Output schema validation failed: {exc}"
    return None


# ---------------------------------------------------------------------------
# Mutation scoring
# ---------------------------------------------------------------------------

def _run_mutation_scoring(
    engine: MutationEngine,
    rule_id: str,
    model_content: str,
    property_content: str,
    jar_path: Path,
    output_dir: Path,
    timeout: int,
) -> Tuple[float, Dict[str, int]]:
    """
    Generate all mutations, run run_rmc on each, return (score, detail).

    A mutant is killed if run_rmc exits with non-zero code.
    Mutations are generated in-memory; each is written to a temp file under ~
    to satisfy safe_path constraints.
    """
    model_strategies = ("transition_bypass", "predicate_flip", "assignment_mutation")
    property_strategies = (
        "comparison_value_mutation",
        "boolean_predicate_negation",
        "assertion_negation",
        "assertion_predicate_inversion",
        "logical_swap",
        "variable_swap",
    )

    # Each strategy returns List[Mutation]; expand into (mutant_model, mutant_property) tuples.
    mutations: list[Tuple[str, str]] = []  # (mutant_model_content, mutant_property_content)

    # Model-side mutations
    for strategy in model_strategies:
        mutant_fn = getattr(engine, strategy, None)
        if mutant_fn is None:
            continue
        try:
            for mut in mutant_fn(model_content, rule_id):
                if mut.mutated_content != model_content:
                    mutations.append((mut.mutated_content, property_content))
        except Exception:
            pass  # strategy not applicable — skip silently

    # Property-side mutations
    for strategy in property_strategies:
        mutant_fn = getattr(engine, strategy, None)
        if mutant_fn is None:
            continue
        try:
            for mut in mutant_fn(property_content, rule_id):
                if mut.mutated_content != property_content:
                    mutations.append((model_content, mut.mutated_content))
        except Exception:
            pass

    total = len(mutations)
    if total == 0:
        return 0.0, {"total": 0, "killed": 0, "survived": 0}

    killed = 0
    home = Path.home()

    for idx, (m_content, p_content) in enumerate(mutations):
        try:
            with tempfile.TemporaryDirectory(dir=home) as tmp:
                tmp_path = Path(tmp)
                m_file = tmp_path / f"mutant_{idx}.rebeca"
                p_file = tmp_path / f"mutant_{idx}.property"
                out_sub = tmp_path / "out"
                out_sub.mkdir()

                m_file.write_text(m_content, encoding="utf-8")
                p_file.write_text(p_content, encoding="utf-8")

                exit_code = run_rmc(
                    jar=str(jar_path),
                    model=str(m_file),
                    property_file=str(p_file),
                    output_dir=str(out_sub),
                    timeout_seconds=timeout,
                )
                if exit_code != 0:
                    killed += 1
        except (Exception, SystemExit):
            # If we can't run the mutant (safe_path exit or other error), treat as survived (conservative)
            pass

    survived = total - killed
    score = round(killed / total * 100.0, 2) if total > 0 else 0.0
    return score, {"total": total, "killed": killed, "survived": survived}


# ---------------------------------------------------------------------------
# Core verification logic
# ---------------------------------------------------------------------------

def run_verification(
    rule_id: str,
    model_path: str,
    property_path: str,
    jar_path: str,
    output_dir: str,
    timeout: int = 120,
) -> Tuple[Dict[str, Any], int]:
    """
    Execute WF-05 verification pipeline.

    Returns (output_dict, exit_code): exit_code 0 = success, 1 = agent failure.
    Non-zero rmc_exit_code is NOT an agent failure — it is a valid verified=false outcome.
    """
    # 1. Validate all paths
    mp, err = _checked_safe_path(model_path, "model_path")
    if err:
        return _error(f"Invalid path: {err}"), 1

    pp, err = _checked_safe_path(property_path, "property_path")
    if err:
        return _error(f"Invalid path: {err}"), 1

    jp, err = _checked_safe_path(jar_path, "jar_path")
    if err:
        return _error(f"Invalid path: {err}"), 1

    od, err = _checked_safe_path(output_dir, "output_dir")
    if err:
        return _error(f"Invalid path: {err}"), 1

    if not mp.exists():
        return _error(f"model_path does not exist: {model_path}"), 1
    if not pp.exists():
        return _error(f"property_path does not exist: {property_path}"), 1
    if not jp.exists():
        return _error(f"jar_path does not exist: {jar_path}"), 1

    od.mkdir(parents=True, exist_ok=True)

    # 2. Run RMC
    try:
        rmc_exit_code = run_rmc(
            jar=str(jp),
            model=str(mp),
            property_file=str(pp),
            output_dir=str(od),
            timeout_seconds=timeout,
        )
    except SystemExit as exc:
        return _error(f"run_rmc called sys.exit({exc.code})"), 1
    except Exception as exc:
        return _error(f"run_rmc raised unexpected exception: {exc}"), 1

    rmc_outcome = _RMC_OUTCOME.get(rmc_exit_code, "unknown")
    verified = rmc_exit_code == 0

    # 3. Null vacuity / mutation defaults for non-zero exit
    vacuity_status: Dict[str, Any] = {
        "is_vacuous":           False,
        "precondition_used":    "",
        "secondary_exit_code":  -1,
        "secondary_output_dir": None,
        "explanation":          "NOT RUN: RMC did not pass (exit_code != 0).",
    }
    mutation_score = 0.0
    mutation_detail: Dict[str, int] = {"total": 0, "killed": 0, "survived": 0}

    if verified:
        # 4. Vacuity check
        try:
            vacuity_result = check_vacuity(
                jar=str(jp),
                model=str(mp),
                property_file=str(pp),
                output_dir=str(od),
                timeout_seconds=timeout,
            )
            vacuity_status = {
                "is_vacuous":           bool(vacuity_result.get("is_vacuous") or False),
                "precondition_used":    vacuity_result.get("precondition_used", ""),
                "secondary_exit_code":  vacuity_result.get("secondary_exit_code", -1),
                "secondary_output_dir": vacuity_result.get("secondary_output_dir"),
                "explanation":          vacuity_result.get("explanation", ""),
            }
        except SystemExit as exc:
            return _error(f"check_vacuity called sys.exit({exc.code})"), 1
        except Exception as exc:
            return _error(f"check_vacuity raised unexpected exception: {exc}"), 1

        # 5. Mutation scoring
        try:
            engine = MutationEngine()
        except Exception as exc:
            return _error(f"MutationEngine instantiation failed: {exc}"), 1

        model_content = mp.read_text(encoding="utf-8")
        property_content = pp.read_text(encoding="utf-8")

        try:
            mutation_score, mutation_detail = _run_mutation_scoring(
                engine=engine,
                rule_id=rule_id,
                model_content=model_content,
                property_content=property_content,
                jar_path=jp,
                output_dir=od,
                timeout=timeout,
            )
        except Exception as exc:
            return _error(f"Mutation scoring failed: {exc}"), 1

    # 6. Build contract
    contract: Dict[str, Any] = {
        "status":           "ok",
        "rule_id":          rule_id,
        "verified":         verified,
        "rmc_exit_code":    rmc_exit_code,
        "rmc_outcome":      rmc_outcome,
        "rmc_output_dir":   str(od),
        "vacuity_status":   vacuity_status,
        "mutation_score":   mutation_score,
        "mutation_detail":  mutation_detail,
        "open_assumptions": list(_OPEN_ASSUMPTIONS),
    }

    # 7. Validate output schema
    if schema_err := _validate_output(contract):
        return _error(schema_err), 1

    return contract, 0


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="verification-agent (WF-05): RMC verification, vacuity check, mutation scoring"
    )
    parser.add_argument("--rule-id",       required=True, help="Rule identifier (e.g. Rule-22)")
    parser.add_argument("--model-path",    required=True, help="Path to .rebeca model file")
    parser.add_argument("--property-path", required=True, help="Path to .property file")
    parser.add_argument("--jar-path",      required=True, help="Path to rmc.jar")
    parser.add_argument("--output-dir",    required=True, help="Directory for RMC artefacts")
    parser.add_argument("--timeout",       type=int, default=120, help="Per-invocation timeout in seconds")

    args = parser.parse_args()

    result, exit_code = run_verification(
        rule_id=args.rule_id,
        model_path=args.model_path,
        property_path=args.property_path,
        jar_path=args.jar_path,
        output_dir=args.output_dir,
        timeout=args.timeout,
    )
    print(json.dumps(result, indent=2))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
