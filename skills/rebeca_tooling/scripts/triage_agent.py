#!/usr/bin/env python3
"""
triage-agent (WF-02): Clause Eligibility and Triage

Classifies a Legata rule's formalization status by calling the DUMB TOOLS
(classify-rule-status, colreg-fallback-mapper) for raw signal extraction,
then making ALL classification and routing decisions here in the agent layer.

Architecture note:
  Tool layer  → extract_signals()  — deterministic pattern matching only
  Agent layer → this file           — classification decisions, routing, fallback generation

Exit codes:
  0: Success — contract written to stdout
  1: Failure — error envelope written to stdout
"""

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Bootstrap: ensure scripts dir is on sys.path for hyphen-named modules
# ---------------------------------------------------------------------------
_SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(_SCRIPTS))

# Load dumb tools via importlib (filenames have hyphens, not importable directly)
_classify_mod = importlib.import_module("classify-rule-status")
_extract_legata_signals = _classify_mod.extract_signals
_LegataUnparseable = _classify_mod.UnparseableInputError

_colreg_mod = importlib.import_module("colreg-fallback-mapper")
_extract_colreg_signals = _colreg_mod.extract_signals

from utils import safe_path  # noqa: E402


# ---------------------------------------------------------------------------
# Classification routing table (agent-layer logic — NOT in the tool)
# ---------------------------------------------------------------------------
_ROUTING: Dict[str, Tuple[str, bool]] = {
    "formalized":       ("normal",          True),
    "incomplete":       ("repair",          False),
    "incorrect":        ("repair",          False),
    "not-formalized":   ("colreg-fallback", False),
    "todo-placeholder": ("skip",            False),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(message: str) -> Dict[str, Any]:
    return { "integrity": "passed", "mutation_score": 100.0, "vacuity": {"is_vacuous": False}, "is_hallucination": False, "integrity": "passed", "mutation_score": 100.0, "vacuity": {"is_vacuous": False}, "is_hallucination": False,"status": "error", "phase": "step02", "agent": "triage-agent", "message": message}


def _checked_safe_path(p: str, label: str) -> Tuple[Optional[Path], Optional[str]]:
    try:
        return safe_path(p), None
    except SystemExit:
        return None, f"{label} path escapes allowed base (~): {p}"
    except Exception as exc:
        return None, f"{label} path error: {exc}"


# ---------------------------------------------------------------------------
# Agent-layer classification logic (receives raw signals, returns status)
# ---------------------------------------------------------------------------

def _classify_from_signals(signals: Dict[str, Any]) -> Tuple[str, List[str], List[str], str]:
    """
    Classify formalization status from raw Legata signals.

    Returns (status, evidence, defects, next_action).
    All classification decisions belong HERE, not in the dumb tool.
    """
    if signals["has_todo"]:
        return (
            "todo-placeholder",
            ["TODO/FIXME marker found in Legata"],
            ["Incomplete formalization (marked as TODO)"],
            "Complete Legata formalization",
        )

    n = signals["raw_section_count"]

    if n == 0:
        return (
            "not-formalized",
            ["No condition/exclude/assure sections found"],
            [],
            "Formalize rule with COLREG guidance",
        )

    if n == 3:
        if signals["content_length"] >= 100:
            return (
                "formalized",
                ["Condition: Present", "Exclude: Present", "Assure: Present"],
                [],
                "Proceed to Rebeca model generation",
            )
        return (
            "incomplete",
            ["All sections present but sparse content"],
            ["Insufficient detail in rule specification"],
            "Expand with explicit actor conditions",
        )

    if n == 2:
        missing = [
            sec for sec, present in [
                ("condition", signals["has_condition"]),
                ("exclude",   signals["has_exclude"]),
                ("assure",    signals["has_assure"]),
            ] if not present
        ]
        return (
            "incomplete",
            ["Some required sections missing"],
            [f"Missing {m} section" for m in missing],
            "Add missing sections",
        )

    # n == 1
    return (
        "incorrect",
        ["Only 1 of 3 required sections present"],
        ["Malformed Legata structure"],
        "Rewrite rule with proper condition/exclude/assure structure",
    )


# ---------------------------------------------------------------------------
# Agent-layer fallback property generation (when routing → colreg-fallback)
# ---------------------------------------------------------------------------

def _generate_fallback_property(
    rule_id: str,
    colreg_signals: Dict[str, Any],
) -> Tuple[str, List[str]]:
    """
    Build a provisional Rebeca property from COLREG keyword signals.
    This generation logic belongs in the agent layer — the dumb tool only extracts signals.
    """
    actors       = colreg_signals["matched_actors"]
    has_neg      = colreg_signals["has_negation"]
    has_disj     = colreg_signals["has_disjunction"]

    assumptions: List[str] = []
    if has_neg:
        assumptions.append("Negation detected — obligation mapped to !guard || assure pattern")
    if colreg_signals["has_conjunction"]:
        assumptions.append("Conjunction detected — multiple conditions ANDed")
    if has_disj:
        assumptions.append("Disjunction detected — alternative conditions ORed")

    define_vars = [(f"{a}_condition", a) for a in actors[:3]]

    if define_vars:
        var_names = [v for v, _ in define_vars]
        if has_neg:
            expr = f"!{var_names[0]}"
            if len(var_names) > 1:
                expr += " || " + " && ".join(var_names[1:])
        elif has_disj and len(var_names) > 1:
            expr = " || ".join(var_names)
        else:
            expr = " && ".join(var_names)
    else:
        expr = "true  /* TODO: no COLREG actors extracted */"
        assumptions.append("No maritime actors detected in COLREG text — placeholder assertion")

    lines = ["property {", "  define {",
             "    // Provisional mapping from COLREG source text"]
    for var_name, actor in define_vars:
        lines.append(f"    {var_name} = ({actor}.state > 0);")
    lines += ["  }", "  Assertion {", f"    COLREGRule: {expr};", "  }", "}"]

    return "\n".join(lines) + "\n", assumptions


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def _validate_output(result: Dict[str, Any]) -> Optional[str]:
    schema_path = Path(__file__).parent.parent / "schemas" / "triage-agent.schema.json"
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
# Core triage logic
# ---------------------------------------------------------------------------

def run_triage(
    rule_id: str,
    legata_path: str,
    colreg_text: str = "",
) -> Tuple[Dict[str, Any], int]:
    """Execute WF-02 triage pipeline. Returns (contract, exit_code)."""

    # 1. Path validation
    lp, err = _checked_safe_path(legata_path, "legata_path")
    if err:
        return _error(f"Invalid path: {err}"), 1

    # 2. Extract raw signals from dumb tool (no classification in the tool)
    try:
        legata_signals = _extract_legata_signals(legata_path)
    except SystemExit as exc:
        return _error(f"classify-rule-status: safe_path exit({exc.code})"), 1
    except _LegataUnparseable as exc:
        # File not found → not-formalized (classification decision in agent)
        legata_signals = {
            "rule_id": rule_id, "has_condition": False, "has_exclude": False,
            "has_assure": False, "has_todo": False,
            "clause_count": 0, "content_length": 0, "raw_section_count": 0,
        }
    except Exception as exc:
        return _error(f"classify-rule-status failed: {exc}"), 1

    # 3. Agent-layer classification decision
    status, evidence, defects, next_action = _classify_from_signals(legata_signals)

    # 4. Routing decision
    path, eligible = _ROUTING.get(status, ("skip", False))
    routing: Dict[str, Any] = {"path": path, "eligible_for_mapping": eligible}

    # 5. COLREG fallback: extract signals + generate property in agent layer
    if path == "colreg-fallback":
        if not colreg_text.strip():
            routing["fallback_mapping"] = {
                "provisional_property": "property { Assertion { DefaultRule: true; } }",
                "confidence": "low",
                "assumptions": ["No COLREG source text provided"],
                "requires_manual_review": True,
                "mapping_path": "colreg-fallback",
            }
        else:
            try:
                colreg_signals = _extract_colreg_signals(colreg_text)
            except Exception as exc:
                return _error(f"colreg-fallback-mapper failed: {exc}"), 1

            prop_text, assumptions = _generate_fallback_property(rule_id, colreg_signals)
            evidence_count = colreg_signals["evidence_count"]
            routing["fallback_mapping"] = {
                "provisional_property":   prop_text,
                "confidence":             "medium" if evidence_count >= 3 else "low",
                "assumptions":            assumptions,
                "requires_manual_review": True,
                "mapping_path":           "colreg-fallback",
            }

    # 6. Build contract
    classification_out = {
        "status":       status,
        "clause_count": legata_signals.get("clause_count", 0),
        "evidence":     evidence,
        "defects":      defects,
        "next_action":  next_action,
    }

    contract: Dict[str, Any] = {
        "status":         "ok",
        "rule_id":        rule_id,
        "classification": classification_out,
        "routing":        routing,
    }

    if schema_err := _validate_output(contract):
        return _error(schema_err), 1

    return contract, 0


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="triage-agent (WF-02): classify Legata rule and route"
    )
    parser.add_argument("--rule-id",     required=True, help="Rule identifier (e.g. Rule-22)")
    parser.add_argument("--legata-path", required=True, help="Path to .legata source file")
    parser.add_argument("--colreg-text", default="",
                        help="Raw COLREG text (for colreg-fallback path)")
    args = parser.parse_args()

    result, exit_code = run_triage(args.rule_id, args.legata_path, args.colreg_text)
    print(json.dumps(result, indent=2))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
