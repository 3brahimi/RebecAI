#!/usr/bin/env python3
"""
triage-agent (WF-02): Clause Eligibility and Triage

Classifies a Legata rule's formalization status via RuleStatusClassifier,
routes it to the correct downstream path, and optionally generates a
COLREG-fallback provisional property.

Exit codes:
  0: Success — full contract written to stdout
  1: Failure — error envelope written to stdout
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Bootstrap: add skills scripts to sys.path
# ---------------------------------------------------------------------------
_SCRIPTS = Path(__file__).parent.parent / "skills" / "rebeca-tooling" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from classify_rule_status import RuleStatusClassifier  # noqa: E402
from colreg_fallback_mapper import COLREGFallbackMapper  # noqa: E402
from utils import safe_path  # noqa: E402


# ---------------------------------------------------------------------------
# Routing table: classifier status → (path, eligible_for_mapping)
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
    """Canonical Error Envelope for WF-02."""
    return {
        "status":  "error",
        "phase":   "step02",
        "agent":   "triage-agent",
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
    Optionally validate result against the JSON Schema.
    Returns an error string on violation, None if valid or jsonschema unavailable.

    Uses the full root schema as the resolver so that $ref to #/definitions/*
    resolves correctly even though we validate against the nested output sub-schema.
    """
    schema_path = Path(__file__).parent / "triage-agent.schema.json"
    try:
        import jsonschema  # type: ignore
        if not schema_path.exists():
            return None
        root_schema = json.loads(schema_path.read_text(encoding="utf-8"))
        output_schema = root_schema.get("output")
        if output_schema:
            # Merge root-level `definitions` into the output sub-schema so that
            # $ref: "#/definitions/…" pointers resolve correctly regardless of
            # which jsonschema version is installed.
            combined = {
                "definitions": root_schema.get("definitions", {}),
                **output_schema,
            }
            errors = list(jsonschema.Draft7Validator(combined).iter_errors(result))
            if errors:
                return f"Output schema validation failed: {errors[0].message}"
    except ImportError:
        pass  # jsonschema not installed — skip validation silently
    except Exception as exc:
        return f"Output schema validation failed: {exc}"
    return None


# ---------------------------------------------------------------------------
# Core triage logic
# ---------------------------------------------------------------------------

def run_triage(
    rule_id: str,
    legata_path: str,
    colreg_text: str,
) -> Tuple[Dict[str, Any], int]:
    """
    Execute WF-02 triage steps.

    Returns (output_dict, exit_code): exit_code 0 = success, 1 = failure.
    output_dict is a success contract or an Error Envelope.
    """
    # 1. Validate legata_path
    lp, err = _checked_safe_path(legata_path, "legata_path")
    if err:
        return _error(f"Invalid path: {err}"), 1

    # 2. Run classifier
    try:
        classifier = RuleStatusClassifier()
        classification = classifier.classify(legata_path)
    except SystemExit as exc:
        # safe_path inside classify() may exit for bad paths
        return _error(f"RuleStatusClassifier failed: path rejected by safe_path (exit {exc.code})"), 1
    except Exception as exc:
        return _error(f"RuleStatusClassifier failed: {exc}"), 1

    raw_status = classification.get("status", "unknown")

    # 3. Map to routing decision
    path, eligible = _ROUTING.get(raw_status, ("skip", False))

    routing: Dict[str, Any] = {
        "path": path,
        "eligible_for_mapping": eligible,
    }

    # 4. COLREG fallback — run mapper
    if path == "colreg-fallback":
        try:
            mapper = COLREGFallbackMapper()
            fallback = mapper.map_rule(rule_id, colreg_text)
            routing["fallback_mapping"] = fallback
        except Exception as exc:
            return _error(f"COLREGFallbackMapper failed: {exc}"), 1

    # 5. Build success contract (strip internal rule_id from classification dict)
    classification_out = {
        "status":       classification.get("status", raw_status),
        "clause_count": classification.get("clause_count", 0),
        "evidence":     classification.get("evidence", []),
        "defects":      classification.get("defects", []),
        "next_action":  classification.get("next_action", ""),
    }

    contract: Dict[str, Any] = {
        "status":         "ok",
        "rule_id":        rule_id,
        "classification": classification_out,
        "routing":        routing,
    }

    # 6. Validate output schema
    if err := _validate_output(contract):
        return _error(err), 1

    return contract, 0


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="triage-agent (WF-02): classify Legata rule and route"
    )
    parser.add_argument(
        "--rule-id", required=True,
        help="Rule identifier (e.g. Rule-22)",
    )
    parser.add_argument(
        "--legata-path", required=True,
        help="Path to the .legata source file",
    )
    parser.add_argument(
        "--colreg-text", default="",
        help="Raw COLREG source text (used when fallback mapping is triggered)",
    )

    args = parser.parse_args()

    result, exit_code = run_triage(
        rule_id=args.rule_id,
        legata_path=args.legata_path,
        colreg_text=args.colreg_text,
    )
    print(json.dumps(result, indent=2))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
