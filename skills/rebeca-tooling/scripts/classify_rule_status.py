#!/usr/bin/env python3
"""
classify-rule-status (DUMB TOOL)

Atomic, deterministic signal extraction from a Legata source file.
Performs ONLY pattern matching — no classification decisions, no routing,
no natural-language interpretation.

Classification decisions (formalized|incomplete|incorrect|not-formalized|todo-placeholder)
are the responsibility of the triage-agent (agent layer).

Exit codes:
  0: Success — JSON signals written to stdout
  2: UnparseableInputError — file not found or not readable
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any

from utils import safe_path, safe_open


class UnparseableInputError(Exception):
    """Raised when the input file cannot be read or parsed deterministically."""


def extract_signals(legata_path: str) -> Dict[str, Any]:
    """
    Extract raw structural signals from a Legata source file.

    Returns a dict of boolean flags and counts — NO classification decisions.

    Raises:
        UnparseableInputError: if the file does not exist or cannot be read.
    """
    path = safe_path(legata_path)
    stem = path.stem

    try:
        with safe_open(legata_path, "r") as f:
            content: str = f.read()
    except FileNotFoundError:
        raise UnparseableInputError(f"Legata file not found: {legata_path}")
    except Exception as exc:
        raise UnparseableInputError(f"Cannot read Legata file: {exc}")

    content_lower = content.lower()

    return {
        "rule_id":           stem,
        "has_condition":     "condition" in content_lower,
        "has_exclude":       "exclude" in content_lower or "exclusion" in content_lower,
        "has_assure":        "assure" in content_lower or "assurance" in content_lower,
        "has_todo":          "todo" in content_lower or "fixme" in content_lower,
        "clause_count":      content.count("clause"),
        "content_length":    len(content.strip()),
        "raw_section_count": sum([
            "condition" in content_lower,
            "exclude" in content_lower or "exclusion" in content_lower,
            "assure" in content_lower or "assurance" in content_lower,
        ]),
    }


class RuleStatusClassifier:
    """
    Thin shim retained for backward-compatibility with existing callers.

    DEPRECATED: classification decisions now belong in the triage-agent.
    This shim calls extract_signals() and re-adds the classification
    fields so callers that expect the old contract do not break immediately.
    Remove once triage-agent.py has been updated.
    """

    def classify(self, legata_path: str) -> Dict[str, Any]:
        try:
            signals = extract_signals(legata_path)
        except UnparseableInputError as exc:
            return {
                "rule_id":      Path(legata_path).stem,
                "status":       "not-formalized",
                "clause_count": 0,
                "evidence":     [str(exc)],
                "defects":      [],
                "next_action":  "Create Legata formalization from COLREG text",
            }

        # Minimal classification delegated from the old implementation.
        # Triage-agent MUST own this logic going forward.
        s = signals
        if s["has_todo"]:
            status, evidence, defects, action = (
                "todo-placeholder",
                ["TODO/FIXME marker found"],
                ["Incomplete formalization (marked as TODO)"],
                "Complete Legata formalization",
            )
        elif s["raw_section_count"] == 0:
            status, evidence, defects, action = (
                "not-formalized",
                ["No condition/exclude/assure sections found"],
                [],
                "Formalize rule with COLREG guidance",
            )
        elif s["raw_section_count"] == 3 and s["content_length"] >= 100:
            status, evidence, defects, action = (
                "formalized",
                ["Condition: Present", "Exclude: Present", "Assure: Present"],
                [],
                "Proceed to Rebeca model generation",
            )
        elif s["raw_section_count"] == 3:
            status, evidence, defects, action = (
                "incomplete",
                ["All sections present but sparse content"],
                ["Insufficient detail"],
                "Expand with explicit actor conditions",
            )
        elif s["raw_section_count"] == 2:
            missing = [
                sec for sec, present in [
                    ("condition", s["has_condition"]),
                    ("exclude", s["has_exclude"]),
                    ("assure", s["has_assure"]),
                ] if not present
            ]
            status, evidence, defects, action = (
                "incomplete",
                ["Some sections missing"],
                [f"Missing {m} section" for m in missing],
                "Add missing sections",
            )
        else:
            status, evidence, defects, action = (
                "incorrect",
                ["Only 1 of 3 required sections present"],
                ["Malformed Legata structure"],
                "Rewrite rule with proper condition/exclude/assure structure",
            )

        return {
            "rule_id":      signals["rule_id"],
            "status":       status,
            "clause_count": signals["clause_count"],
            "evidence":     evidence,
            "defects":      defects,
            "next_action":  action,
        }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="classify-rule-status: extract raw Legata signals (dumb tool)"
    )
    parser.add_argument("--legata-path", required=True, help="Path to .legata source file")
    args = parser.parse_args()

    try:
        signals = extract_signals(args.legata_path)
        print(json.dumps({"status": "ok", **signals}, indent=2))
        sys.exit(0)
    except UnparseableInputError as exc:
        print(json.dumps({
            "status":  "error",
            "code":    2,
            "message": str(exc),
        }, indent=2))
        sys.exit(2)


if __name__ == "__main__":
    main()
