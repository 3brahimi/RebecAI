#!/usr/bin/env python3
"""
mapping-agent (WF-04): Manual Mapping Core

Consumes the WF-03 abstraction_summary and produces two Timed Rebeca artifacts:
  - {rule_id}.rebeca  — actor model with statevars
  - {rule_id}.property — property file with define block + canonical assertion

Canonical assertion pattern (per transformation_patterns.md):
  RuleN: !condition || exclusion || (assurance1 && assurance2);

Exit codes:
  0: Success — full contract written to stdout
  1: Failure — error envelope written to stdout
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

from utils import safe_path  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_QUEUE_SIZE = 10
_DEFAULT_INT = 0
_DEFAULT_BOOL = "false"

# Legata section text operators and values
_THRESHOLD_RE = re.compile(
    r"(?:meters?|miles?|knots?|nm|m)?\(?\s*(\d+(?:\.\d+)?)\s*\)?",
    re.IGNORECASE,
)
_OPERATOR_RE = re.compile(r"(>=|<=|==|>|<)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(message: str) -> Dict[str, Any]:
    return {"status": "error", "phase": "step04", "agent": "mapping-agent", "message": message}


def _checked_safe_path(p: str, label: str) -> Tuple[Optional[Path], Optional[str]]:
    try:
        return safe_path(p), None
    except SystemExit:
        return None, f"{label} path escapes allowed base (~): {p}"
    except Exception as exc:
        return None, f"{label} path error: {exc}"


def _validate_output(result: Dict[str, Any]) -> Optional[str]:
    schema_path = Path(__file__).parent / "mapping-agent.schema.json"
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
# Threshold extraction from Legata concept text
# ---------------------------------------------------------------------------

def _extract_threshold(concept_text: str) -> Tuple[str, int]:
    """
    Parse a Legata concept string for a comparison operator and numeric threshold.

    Returns (operator, threshold):
      e.g. ">= miles(6)"  → (">=", 6)
           "> meters(50)" → (">",  50)
           "some boolean" → (">",   0)   ← default
    """
    op_match = _OPERATOR_RE.search(concept_text)
    op = op_match.group(1) if op_match else ">"

    num_match = _THRESHOLD_RE.search(concept_text)
    threshold = int(float(num_match.group(1))) if num_match else 0

    return op, threshold


# ---------------------------------------------------------------------------
# Define expression builder
# ---------------------------------------------------------------------------

def _define_expression(
    instance: str,
    var: Dict[str, Any],
    concept_text: str,
) -> str:
    """
    Build the RHS expression for a property `define` alias.

    boolean: ({instance}.{name} == true)
    int:     ({instance}.{name} {op} {threshold})
    """
    name = var["rebeca_name"]
    if var["rebeca_type"] == "boolean":
        return f"({instance}.{name} == true)"
    else:
        op, threshold = _extract_threshold(concept_text)
        return f"({instance}.{name} {op} {threshold})"


# ---------------------------------------------------------------------------
# Model file generator
# ---------------------------------------------------------------------------

def _generate_model(
    actor_map: List[Dict[str, Any]],
    variable_map: List[Dict[str, Any]],
) -> str:
    """
    Produce the full .rebeca source for all actors in actor_map.

    Each actor gets all non-inferred state variables. The constructor
    initialises them to type defaults. msgsrv tick() is left empty as a
    placeholder for domain-specific state transitions.
    """
    # Include all variables (inferred vars belong to the actor too)
    live_vars = [v for v in variable_map]

    blocks: List[str] = []

    for actor in actor_map:
        cls = actor["rebeca_class"]
        inst = actor["rebeca_instance"]

        # statevars block
        statevar_lines: List[str] = []
        for v in live_vars:
            statevar_lines.append(f"    {v['rebeca_type']} {v['rebeca_name']};")

        # constructor body
        ctor_lines: List[str] = []
        for v in live_vars:
            default = _DEFAULT_BOOL if v["rebeca_type"] == "boolean" else str(_DEFAULT_INT)
            ctor_lines.append(f"    {v['rebeca_name']} = {default};")

        class_body = [
            f"reactiveclass {cls}({_QUEUE_SIZE}) {{",
            "  statevars {",
        ]
        class_body.extend(f"  {ln}" for ln in statevar_lines)
        class_body.append("  }")
        class_body.append(f"  {cls}() {{")
        class_body.extend(f"  {ln}" for ln in ctor_lines)
        class_body.append("  }")
        class_body.append("  msgsrv tick() {")
        class_body.append("  }")
        class_body.append("}")
        blocks.append("\n".join(class_body))

    # main block — one instance per actor
    main_lines = ["main {"]
    for actor in actor_map:
        main_lines.append(f"  {actor['rebeca_class']} {actor['rebeca_instance']}():();")
    main_lines.append("}")

    return "\n".join(blocks) + "\n" + "\n".join(main_lines) + "\n"


# ---------------------------------------------------------------------------
# Property file generator
# ---------------------------------------------------------------------------

def _generate_property(
    rule_id: str,
    actor_map: List[Dict[str, Any]],
    variable_map: List[Dict[str, Any]],
    open_assumptions: List[str],
) -> str:
    """
    Produce the full .property source.

    define block: one alias per variable (all sources).
    Assertion:    !condition || exclusion || (assurance1 && assurance2)
    """
    # Use first actor's instance for all defines (single-actor canonical form)
    instance = actor_map[0]["rebeca_instance"] if actor_map else "actor"

    define_lines: List[str] = []
    for v in variable_map:
        expr = _define_expression(instance, v, v["legata_concept"])
        define_lines.append(f"    {v['define_alias']} = {expr};")

    # Collect aliases by source role
    conditions = [v["define_alias"] for v in variable_map if v["source"] == "condition"]
    exclusions = [v["define_alias"] for v in variable_map if v["source"] == "exclusion"]
    assurances = [v["define_alias"] for v in variable_map if v["source"] == "assurance"]

    # Build assertion RHS: !c1 || !c2 || exc1 || exc2 || (a1 && a2)
    terms: List[str] = []
    for c in conditions:
        terms.append(f"!{c}")
    for e in exclusions:
        terms.append(e)
    if len(assurances) > 1:
        terms.append(f"({'  &&  '.join(assurances)})")
    elif assurances:
        terms.append(assurances[0])

    # Fallback: if no terms at all, produce a trivially-true placeholder
    if not terms:
        terms = ["true  /* TODO: no condition/assurance extracted */"]
        open_assumptions.append(
            "Assertion body is a placeholder — no condition/exclusion/assurance found in variable_map"
        )

    # Canonical rule name: strip hyphens so 'Rule-22' → 'Rule22'
    rule_name = rule_id.replace("-", "")
    assertion_rhs = " || ".join(terms)

    lines = [
        "property {",
        "  define {",
    ]
    lines.extend(define_lines)
    lines.append("  }")
    lines.append("  Assertion {")
    lines.append(f"    {rule_name}: {assertion_rhs};")
    lines.append("  }")
    lines.append("}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Core mapping logic
# ---------------------------------------------------------------------------

def run_mapping(
    rule_id: str,
    legata_path: str,
    abstraction_summary: Dict[str, Any],
    output_dir: str,
) -> Tuple[Dict[str, Any], int]:
    """
    Execute WF-04 mapping steps.
    Returns (output_dict, exit_code).
    """
    # 1. Validate paths
    lp, err = _checked_safe_path(legata_path, "legata_path")
    if err:
        return _error(f"Invalid path: {err}"), 1

    od, err = _checked_safe_path(output_dir, "output_dir")
    if err:
        return _error(f"Invalid path: {err}"), 1

    assert lp is not None and od is not None

    # 2. Validate abstraction_summary structure
    actor_map: List[Dict[str, Any]] = abstraction_summary.get("actor_map", [])
    variable_map: List[Dict[str, Any]] = abstraction_summary.get("variable_map", [])

    if not actor_map and not variable_map:
        return _error(
            "Invalid abstraction_summary: both actor_map and variable_map are empty"
        ), 1

    # Provide a default actor when the summary has variables but no actors
    if not actor_map:
        actor_map = [{"legata_actor": "actor", "rebeca_class": "Actor", "rebeca_instance": "actor"}]

    # 3. Collect open_assumptions (carry forward any from the summary)
    open_assumptions: List[str] = []

    # Flag int variables where threshold will default to 0
    for v in variable_map:
        if v["rebeca_type"] == "int":
            concept = v.get("legata_concept", "")
            _, threshold = _extract_threshold(concept)
            if threshold == 0 and not re.search(r"\b0\b", concept):
                open_assumptions.append(
                    f"Threshold for '{v['rebeca_name']}' defaulted to > 0 "
                    f"— refine manually from: \"{concept}\""
                )

    # 4. Generate model and property content
    model_content = _generate_model(actor_map, variable_map)
    property_content = _generate_property(rule_id, actor_map, variable_map, open_assumptions)

    # 5. Write artifacts
    try:
        od.mkdir(parents=True, exist_ok=True)
        model_path = od / f"{rule_id}.rebeca"
        prop_path  = od / f"{rule_id}.property"
        model_path.write_text(model_content, encoding="utf-8")
        prop_path.write_text(property_content, encoding="utf-8")
    except Exception as exc:
        return _error(f"Failed to write artifact: {exc}"), 1

    # 6. Build and validate contract
    contract: Dict[str, Any] = {
        "status": "ok",
        "rule_id": rule_id,
        "model_artifact": {
            "path": str(model_path.resolve()),
            "content": model_content,
        },
        "property_artifact": {
            "path": str(prop_path.resolve()),
            "content": property_content,
        },
        "open_assumptions": open_assumptions,
    }

    if err := _validate_output(contract):
        return _error(err), 1

    return contract, 0


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="mapping-agent (WF-04): generate Rebeca model + property from abstraction"
    )
    parser.add_argument("--rule-id",          required=True, help="Rule identifier (e.g. Rule-22)")
    parser.add_argument("--legata-path",      required=True, help="Path to .legata source file")
    parser.add_argument("--abstraction-json", required=True,
                        help="JSON string or @path for the WF-03 abstraction_summary")
    parser.add_argument("--output-dir",       required=True, help="Directory for generated artifacts")

    args = parser.parse_args()

    # Support both inline JSON and @path-to-file
    raw = args.abstraction_json
    if raw.startswith("@"):
        try:
            abs_path, err = _checked_safe_path(raw[1:], "abstraction-json file")
            if err:
                print(json.dumps(_error(f"Invalid path: {err}")), indent=2)
                sys.exit(1)
            assert abs_path is not None
            raw = abs_path.read_text(encoding="utf-8")
        except Exception as exc:
            print(json.dumps(_error(f"Cannot read abstraction JSON file: {exc}"), indent=2))
            sys.exit(1)

    try:
        abstraction_summary = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps(_error(f"Invalid abstraction_summary JSON: {exc}"), indent=2))
        sys.exit(1)

    result, exit_code = run_mapping(
        rule_id=args.rule_id,
        legata_path=args.legata_path,
        abstraction_summary=abstraction_summary,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
