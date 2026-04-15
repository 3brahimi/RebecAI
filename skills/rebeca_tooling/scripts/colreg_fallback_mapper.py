#!/usr/bin/env python3
"""
colreg-fallback-mapper (DUMB TOOL)

Atomic, deterministic keyword and pattern extraction from COLREG source text.
Performs ONLY regex/keyword matching — no Rebeca property generation,
no confidence assessment, no routing decisions.

Property generation from extracted signals is the responsibility of the
triage-agent (agent layer).

Exit codes:
  0: Success — JSON signals written to stdout
  2: UnparseableInputError — input text is empty or non-string
"""

import json
import re
import sys
from typing import Any, Dict, List


class UnparseableInputError(Exception):
    """Raised when COLREG input text cannot be deterministically processed."""


# Deterministic keyword lists — no NL interpretation
_MARITIME_ACTORS: List[str] = [
    "vessel", "ship", "boat", "aircraft",
    "light", "shape", "signal", "whistle",
    "visibility", "darkness", "fog",
]

_OBLIGATION_PATTERNS: List[str] = [
    r"\bshall not\b",
    r"\bmust not\b",
    r"\bnot\b",
]

_CONJUNCTION_PATTERNS: List[str] = [r"\band\b"]
_DISJUNCTION_PATTERNS: List[str] = [r"\bor\b"]

# Numeric literals adjacent to units (for threshold extraction only)
_NUMERIC_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:meters?|miles?|knots?|nm|m|degrees?|nautical)",
    re.IGNORECASE,
)


def extract_signals(colreg_text: str) -> Dict[str, Any]:
    """
    Extract raw keyword and pattern signals from COLREG rule text.

    Returns a dict of matched actors, boolean flags, and numeric literals.
    Makes NO classification or routing decisions.

    Raises:
        UnparseableInputError: if text is empty or not a string.
    """
    if not isinstance(colreg_text, str):
        raise UnparseableInputError("colreg_text must be a string")
    if not colreg_text.strip():
        raise UnparseableInputError("colreg_text is empty — no signals to extract")

    text_lower = colreg_text.lower()

    # Actor keyword matches (deterministic list scan)
    matched_actors: List[str] = [
        kw for kw in _MARITIME_ACTORS if kw in text_lower
    ]

    # Obligation / conjunction / disjunction flags (regex)
    has_negation = any(
        re.search(p, text_lower) for p in _OBLIGATION_PATTERNS
    )
    has_conjunction = any(
        re.search(p, text_lower) for p in _CONJUNCTION_PATTERNS
    )
    has_disjunction = any(
        re.search(p, text_lower) for p in _DISJUNCTION_PATTERNS
    )

    # Numeric literals with maritime units
    numeric_matches = [
        {"value": float(m.group(1)), "context": m.group(0)}
        for m in _NUMERIC_RE.finditer(colreg_text)
    ]

    evidence_count = len(matched_actors) + sum([has_negation, has_conjunction, has_disjunction])

    return {
        "matched_actors":    matched_actors,
        "has_negation":      has_negation,
        "has_conjunction":   has_conjunction,
        "has_disjunction":   has_disjunction,
        "numeric_matches":   numeric_matches,
        "evidence_count":    evidence_count,
        "input_length":      len(colreg_text.strip()),
    }


class COLREGFallbackMapper:
    """
    Thin shim retained for backward-compatibility with existing callers.

    DEPRECATED: property generation from COLREG signals now belongs in the
    triage-agent (agent layer). Remove once triage-agent.py is updated.
    """

    def map_rule(self, rule_id: str, colreg_text: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "rule_id":              rule_id,
            "provisional_property": "",
            "confidence":           "low",
            "assumptions":          [],
            "requires_manual_review": True,
            "mapping_path":         "colreg-fallback",
        }

        if not colreg_text or not colreg_text.strip():
            result["provisional_property"] = (
                "property { Assertion { DefaultRule: true; } }"
            )
            result["assumptions"].append("No COLREG source text provided")
            return result

        try:
            signals = extract_signals(colreg_text)
        except UnparseableInputError:
            result["provisional_property"] = (
                "property { Assertion { DefaultRule: true; } }"
            )
            result["assumptions"].append("COLREG text could not be parsed")
            return result

        actors = signals["matched_actors"]
        has_negation = signals["has_negation"]
        has_conjunction = signals["has_conjunction"]
        has_disjunction = signals["has_disjunction"]

        if has_negation:
            result["assumptions"].append(
                "Negation detected — obligation mapped to !guard || assure pattern"
            )
        if has_conjunction:
            result["assumptions"].append("Conjunction detected — conditions ANDed")
        if has_disjunction:
            result["assumptions"].append("Disjunction detected — conditions ORed")

        define_vars = [(f"{a}_condition", a) for a in actors[:3]]

        if define_vars:
            var_names = [v for v, _ in define_vars]
            if has_negation:
                assertion_expr = f"!{var_names[0]}"
                if len(var_names) > 1:
                    assertion_expr += " || " + " && ".join(var_names[1:])
            elif has_disjunction and len(var_names) > 1:
                assertion_expr = " || ".join(var_names)
            else:
                assertion_expr = " && ".join(var_names)
        else:
            assertion_expr = "true"

        lines = [
            "property {",
            "  define {",
            "    // Provisional mapping from COLREG source text",
        ]
        for var_name, actor in define_vars:
            lines.append(f"    {var_name} = ({actor}.state > 0);")
        lines.extend([
            "  }",
            "  Assertion {",
            f"    COLREGRule: {assertion_expr};",
            "  }",
            "}",
        ])
        result["provisional_property"] = "\n".join(lines)

        evidence_count = signals["evidence_count"]
        result["confidence"] = "medium" if evidence_count >= 3 else "low"

        return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="colreg-fallback-mapper: extract COLREG keyword signals (dumb tool)"
    )
    parser.add_argument("--colreg-text", required=True, help="Raw COLREG rule text")
    args = parser.parse_args()

    try:
        signals = extract_signals(args.colreg_text)
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
