#!/usr/bin/env python3
"""
Vacuity Checker for Rebeca property verification.

Performs a secondary RMC pass that asserts !Precondition to confirm a property
is not passing trivially due to an impossible precondition.

Algorithm:
  1. Extract the first assertion expression from the Assertion block.
  2. Generate a negated-precondition property: Assertion { VacuityCheck: !Precondition; }
  3. Run RMC on the original model with the negated property.
  4. exit_code == 0  → !Precondition verified → original property was VACUOUS.
  5. exit_code != 0  → counterexample found  → original property is NON-VACUOUS (good).

Exit codes:
  0: Non-vacuous — property is meaningful
  1: Invalid inputs or runtime error
  2: Vacuous — property passes trivially (precondition is never reachable)
  3: Secondary RMC timeout
  4: Secondary RMC C++ compilation failure
  5: Secondary RMC parse failure
"""

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from run_rmc import run_rmc
from utils import safe_path


def extract_precondition(property_content: str) -> Optional[str]:
    """
    Extract the first assertion expression from the Assertion block.

    Example:
      Assertion { Rule22: !hasLight || (lightRange >= 6); }
      → "!hasLight || (lightRange >= 6)"

    Returns the expression string, or None if the block cannot be parsed.
    """
    m = re.search(
        r'\bAssertion\s*\{[^}]*?\w+\s*:\s*(!?)(.+?);',
        property_content,
        re.DOTALL,
    )
    if m is None:
        return None
    return (m.group(1) + m.group(2)).strip()


def build_negated_property(property_content: str, precondition: str) -> str:
    """
    Replace the Assertion block body with a single assertion of !Precondition.

    Simplifies double-negation: if precondition already starts with '!', the
    negated form becomes the positive expression. Preserves the define block
    and LTL block unchanged.
    """
    if precondition.startswith('!'):
        # Remove leading '!' and optional surrounding parens
        inner = precondition[1:].strip()
        negated = inner[1:-1] if (inner.startswith('(') and inner.endswith(')')) else inner
    else:
        negated = f"!({precondition})"

    negated_assertion = f"\n    VacuityCheck: {negated};\n  "
    return re.sub(
        r'(\bAssertion\s*\{)[^}]*(\})',
        lambda m: m.group(1) + negated_assertion + m.group(2),
        property_content,
        count=1,
        flags=re.DOTALL,
    )


def check_vacuity(
    jar: str,
    model: str,
    property_file: str,
    output_dir: str,
    timeout_seconds: int = 120,
) -> Dict[str, Any]:
    """
    Perform a vacuity check on a verified Rebeca property.

    Wraps run_rmc() — does not modify existing verification artifacts.
    Secondary RMC output is written to output_dir + "_vacuity/".

    Returns:
        {
          "is_vacuous":            bool | None,
          "precondition_used":     str | None,
          "secondary_exit_code":   int,
          "secondary_output_dir":  str | None,
          "explanation":           str
        }
    """
    prop_path = safe_path(property_file)
    if not prop_path.exists():
        return {
            "is_vacuous": None,
            "precondition_used": None,
            "secondary_exit_code": 1,
            "secondary_output_dir": None,
            "explanation": f"Property file not found: {property_file}",
        }

    property_content = prop_path.read_text(encoding="utf-8")
    precondition = extract_precondition(property_content)

    if precondition is None:
        return {
            "is_vacuous": None,
            "precondition_used": None,
            "secondary_exit_code": 1,
            "secondary_output_dir": None,
            "explanation": "Could not extract precondition from Assertion block",
        }

    negated_content = build_negated_property(property_content, precondition)
    secondary_output = str(safe_path(output_dir)) + "_vacuity"

    # Write the negated property to a temp file inside ~ so safe_path() allows it.
    # Always clean up afterwards.
    tmp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".property", delete=False, encoding="utf-8",
            dir=Path.home(),
        ) as tmp:
            tmp.write(negated_content)
            tmp_path = Path(tmp.name)

        exit_code = run_rmc(
            jar=jar,
            model=model,
            property_file=str(tmp_path),
            output_dir=secondary_output,
            timeout_seconds=timeout_seconds,
        )
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)

    # exit_code == 0: !Precondition verified → precondition impossible → vacuous
    # exit_code != 0: counterexample found  → precondition reachable  → non-vacuous
    is_vacuous = exit_code == 0

    return {
        "is_vacuous": is_vacuous,
        "precondition_used": precondition,
        "secondary_exit_code": exit_code,
        "secondary_output_dir": secondary_output,
        "explanation": (
            "VACUOUS: The property passes trivially — its precondition is never reachable."
            if is_vacuous
            else "NON-VACUOUS: A counterexample exists for !Precondition; the property is meaningful."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Vacuity check: verify a Rebeca property is not passing trivially"
    )
    parser.add_argument("--jar", required=True, help="Path to rmc.jar")
    parser.add_argument("--model", required=True, help="Path to .rebeca model file")
    parser.add_argument("--property", required=True, help="Path to .property file")
    parser.add_argument(
        "--output-dir", required=True, help="Base output directory (appends _vacuity/)"
    )
    parser.add_argument(
        "--timeout-seconds", type=int, default=120, help="RMC timeout in seconds"
    )
    parser.add_argument("--output-json", action="store_true", help="Output result as JSON")
    args = parser.parse_args()

    result = check_vacuity(
        jar=args.jar,
        model=args.model,
        property_file=args.property,
        output_dir=args.output_dir,
        timeout_seconds=args.timeout_seconds,
    )

    if args.output_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Precondition:            {result['precondition_used']}")
        print(f"Is Vacuous:              {result['is_vacuous']}")
        print(f"Secondary RMC exit code: {result['secondary_exit_code']}")
        print(f"Explanation:             {result['explanation']}")
        if result["secondary_output_dir"]:
            print(f"Secondary output dir:    {result['secondary_output_dir']}")

    if result["is_vacuous"] is True:
        sys.exit(2)
    elif result["is_vacuous"] is False:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
