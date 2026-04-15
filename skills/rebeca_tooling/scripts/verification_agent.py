#!/usr/bin/env python3
"""
verification-agent (WF-06): RMC Verification, Vacuity Check, Mutation Scoring

Orchestrates:
  1. run_rmc      — compile .rebeca + .property → exit code classification
  2. check_vacuity — vacuity check (only when rmc_exit_code == 0)
  3. MutationEngine — mutation scoring (only when rmc_exit_code == 0)

Exit codes:
  0: Success — full contract written to stdout
  1: Failure — error envelope written to stdout
"""

import argparse
import importlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
_SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(_SCRIPTS))

_rmc_mod      = importlib.import_module("run-rmc")
_vacuity_mod  = importlib.import_module("vacuity-checker")
_mutation_mod = importlib.import_module("mutation-engine")

run_rmc       = _rmc_mod.run_rmc
check_vacuity = _vacuity_mod.check_vacuity
MutationEngine = _mutation_mod.MutationEngine

from utils import safe_path  # noqa: E402


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

_MODEL_STRATEGIES: Tuple[str, ...] = (
    "transition_bypass", "predicate_flip", "assignment_mutation",
)
_PROPERTY_STRATEGIES: Tuple[str, ...] = (
    "comparison_value_mutation", "boolean_predicate_negation",
    "assertion_negation", "assertion_predicate_inversion",
    "logical_swap", "variable_swap",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(message: str) -> Dict[str, Any]:
    return {
        "status": "error", "phase": "step06",
        "agent": "verification-agent", "message": message,
    }


def _checked_safe_path(p: str, label: str) -> Tuple[Optional[Path], Optional[str]]:
    try:
        return safe_path(p), None
    except SystemExit:
        return None, f"{label} path escapes allowed base (~): {p}"
    except Exception as exc:
        return None, f"{label} path error: {exc}"


def _validate_output(result: Dict[str, Any]) -> Optional[str]:
    schema_path = Path(__file__).parent.parent / "schemas" / "verification-agent.schema.json"
    try:
        import jsonschema  # type: ignore
        if not schema_path.exists():
            return None
        root = json.loads(schema_path.read_text(encoding="utf-8"))
        output_schema = root.get("output")
        if output_schema:
            combined = {"definitions": root.get("definitions", {}), **output_schema}
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
    engine: Any,
    rule_id: str,
    model_content: str,
    property_content: str,
    jar_path: Path,
    output_dir: Path,
    timeout: int,
) -> Tuple[float, Dict[str, int]]:
    mutations: List[Tuple[str, str]] = []

    for strategy in _MODEL_STRATEGIES:
        fn = getattr(engine, strategy, None)
        if fn is None:
            continue
        try:
            for mut in fn(model_content, rule_id):
                if mut.mutated_content != model_content:
                    mutations.append((mut.mutated_content, property_content))
        except Exception:
            pass

    for strategy in _PROPERTY_STRATEGIES:
        fn = getattr(engine, strategy, None)
        if fn is None:
            continue
        try:
            for mut in fn(property_content, rule_id):
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
                m_file   = tmp_path / f"mutant_{idx}.rebeca"
                p_file   = tmp_path / f"mutant_{idx}.property"
                out_sub  = tmp_path / "out"
                out_sub.mkdir()
                m_file.write_text(m_content, encoding="utf-8")
                p_file.write_text(p_content, encoding="utf-8")
                ec = run_rmc(str(jar_path), str(m_file), str(p_file),
                             str(out_sub), timeout)
                if ec != 0:
                    killed += 1
        except (Exception, SystemExit):
            pass  # treat as survived (conservative)

    score = round(killed / total * 100.0, 2)
    return score, {"total": total, "killed": killed, "survived": total - killed}


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

    mp, err = _checked_safe_path(model_path,    "model_path");    _ = err and (None, 1)
    pp, err = _checked_safe_path(property_path, "property_path"); _ = err and (None, 1)
    jp, err = _checked_safe_path(jar_path,      "jar_path");      _ = err and (None, 1)
    od, err = _checked_safe_path(output_dir,    "output_dir");    _ = err and (None, 1)

    for path_val, label, original in [
        (mp, "model_path",    model_path),
        (pp, "property_path", property_path),
        (jp, "jar_path",      jar_path),
        (od, "output_dir",    output_dir),
    ]:
        if path_val is None:
            return _error(f"Invalid path: {label} escapes allowed base (~): {original}"), 1

    assert mp and pp and jp and od  # narrowing for type checker

    for p, label in [(mp, "model_path"), (pp, "property_path"), (jp, "jar_path")]:
        if not p.exists():
            return _error(f"{label} not found: {p}"), 1

    od.mkdir(parents=True, exist_ok=True)

    try:
        rmc_exit_code = run_rmc(str(jp), str(mp), str(pp), str(od), timeout)
    except SystemExit as exc:
        return _error(f"run_rmc called sys.exit({exc.code})"), 1
    except Exception as exc:
        return _error(f"run_rmc raised unexpected exception: {exc}"), 1

    rmc_outcome = _RMC_OUTCOME.get(rmc_exit_code, "unknown")
    verified    = rmc_exit_code == 0

    vacuity_status: Dict[str, Any] = {
        "is_vacuous": False, "precondition_used": "",
        "secondary_exit_code": -1, "secondary_output_dir": None,
        "explanation": "NOT RUN: RMC did not pass (exit_code != 0).",
    }
    mutation_score  = 0.0
    mutation_detail: Dict[str, int] = {"total": 0, "killed": 0, "survived": 0}

    if verified:
        try:
            vr = check_vacuity(str(jp), str(mp), str(pp), str(od), timeout)
            vacuity_status = {
                "is_vacuous":           bool(vr.get("is_vacuous") or False),
                "precondition_used":    vr.get("precondition_used", ""),
                "secondary_exit_code":  vr.get("secondary_exit_code", -1),
                "secondary_output_dir": vr.get("secondary_output_dir"),
                "explanation":          vr.get("explanation", ""),
            }
        except SystemExit as exc:
            return _error(f"check_vacuity called sys.exit({exc.code})"), 1
        except Exception as exc:
            return _error(f"check_vacuity raised unexpected exception: {exc}"), 1

        try:
            engine = MutationEngine()
        except Exception as exc:
            return _error(f"MutationEngine instantiation failed: {exc}"), 1

        try:
            mutation_score, mutation_detail = _run_mutation_scoring(
                engine, rule_id,
                mp.read_text(encoding="utf-8"),
                pp.read_text(encoding="utf-8"),
                jp, od, timeout,
            )
        except Exception as exc:
            return _error(f"Mutation scoring failed: {exc}"), 1

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

    if schema_err := _validate_output(contract):
        return _error(schema_err), 1

    return contract, 0


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="verification-agent (WF-06): RMC verification, vacuity, mutation scoring"
    )
    parser.add_argument("--rule-id",       required=True)
    parser.add_argument("--model-path",    required=True)
    parser.add_argument("--property-path", required=True)
    parser.add_argument("--jar-path",      required=True)
    parser.add_argument("--output-dir",    required=True)
    parser.add_argument("--timeout", type=int, default=120)

    args = parser.parse_args()
    result, exit_code = run_verification(
        args.rule_id, args.model_path, args.property_path,
        args.jar_path, args.output_dir, args.timeout,
    )
    print(json.dumps(result, indent=2))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
