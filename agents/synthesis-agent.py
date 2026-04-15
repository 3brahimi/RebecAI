#!/usr/bin/env python3
"""
llm-lane-agent (WF-06): LLM-Assisted Candidate Property Generation

Runs in parallel with WF-04 (mapping-agent) after WF-03 completes.
Generates two candidate formulations from the same abstraction_summary:

  Strategy 'base'     — same !condition || exclusion || assurance pattern as
                        WF-04, with per-actor queue sizing from statevar count.
  Strategy 'temporal' — wraps the base assertion in LTL { G(assertion); }
                        for temporal model checkers.

ALL outputs carry:
  mapping_path: "llm-lane"
  is_candidate: true   ← coordinator MUST route to WF-05 before promotion

Exit codes:
  0: Success — contract written to stdout
  1: Failure — error envelope written to stdout
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Bootstrap: add skills scripts to sys.path
# ---------------------------------------------------------------------------
_SCRIPTS = Path(__file__).parent.parent / "skills" / "rebeca-tooling" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from utils import safe_path  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(message: str) -> Dict[str, Any]:
    """Canonical Error Envelope for WF-06."""
    return {
        "status":  "error",
        "phase":   "step06",
        "agent":   "llm-lane-agent",
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
    """Validate result against the output sub-schema."""
    schema_path = Path(__file__).parent / "llm-lane-agent.schema.json"
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
# Model generation (shared by both strategies)
# ---------------------------------------------------------------------------

def _generate_model(
    actor_map: List[Dict[str, Any]],
    variable_map: List[Dict[str, Any]],
) -> str:
    """
    Generate a .rebeca model from the abstraction summary.

    Difference from WF-04: queue size is derived from the number of statevars
    owned by each actor (minimum 1), rather than a fixed constant.
    """
    lines: List[str] = []

    for actor in actor_map:
        cls = actor["rebeca_class"]
        # Count statevars belonging to this actor — all vars in the simplified
        # model are owned by the single (or first) actor class.
        statevar_count = max(1, len(variable_map))
        queue_size = statevar_count + 1  # +1 for the tick message

        statevars = []
        for v in variable_map:
            if v["rebeca_type"] == "boolean":
                statevars.append(f"        boolean {v['rebeca_name']} = false;")
            else:
                statevars.append(f"        int {v['rebeca_name']} = 0;")

        statevar_block = "\n".join(statevars) if statevars else "        // no state variables"

        lines.append(f"reactiveclass {cls}({queue_size}) {{")
        lines.append(f"    statevars {{")
        lines.append(statevar_block)
        lines.append(f"    }}")
        lines.append(f"    {cls}() {{")
        lines.append(f"    }}")
        lines.append(f"    msgsrv tick() {{")
        lines.append(f"    }}")
        lines.append(f"}}")
        lines.append("")

    # main block
    lines.append("main {")
    for actor in actor_map:
        lines.append(f"    {actor['rebeca_class']} {actor['rebeca_instance']}({actor['rebeca_instance']});")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Property generation (shared define block, two assertion strategies)
# ---------------------------------------------------------------------------

def _build_define_lines(
    variable_map: List[Dict[str, Any]],
    actor_map: List[Dict[str, Any]],
) -> Tuple[List[str], List[str]]:
    """
    Return (define_lines, open_assumptions).

    Reuses the same define expression logic as WF-04 to keep candidates
    structurally comparable to the manual lane output.
    """
    define_lines: List[str] = []
    open_assumptions: List[str] = []

    if not actor_map:
        return define_lines, ["No actors in abstraction_summary — define block is empty"]

    instance = actor_map[0]["rebeca_instance"]

    for v in variable_map:
        name = v["rebeca_name"]
        alias = v["define_alias"]
        rtype = v["rebeca_type"]

        if rtype == "boolean":
            expr = f"{instance}.{name} == true"
        else:
            # int: use > 0 as a conservative threshold when no richer hint available
            concept = v.get("legata_concept", "")
            threshold_match = re.search(r"\b(\d+)\b", concept)
            threshold = int(threshold_match.group(1)) if threshold_match else 0
            expr = f"{instance}.{name} > {threshold}"
            if threshold == 0 and not re.search(r"\b0\b", concept):
                open_assumptions.append(
                    f"Threshold for '{name}' defaulted to > 0 "
                    f"— refine from: \"{concept}\""
                )

        define_lines.append(f"    {alias} = ({expr});")

    return define_lines, open_assumptions


def _build_assertion_rhs(variable_map: List[Dict[str, Any]]) -> str:
    """
    Build canonical !condition || exclusion || assurance RHS.
    Returns 'true' placeholder when variable_map is empty.
    """
    conditions  = [v["define_alias"] for v in variable_map if v["source"] == "condition"]
    exclusions  = [v["define_alias"] for v in variable_map if v["source"] == "exclusion"]
    assurances  = [v["define_alias"] for v in variable_map if v["source"] == "assurance"]

    terms: List[str] = []
    for c in conditions:
        terms.append(f"!{c}")
    for e in exclusions:
        terms.append(e)
    if len(assurances) > 1:
        terms.append(f"({'  &&  '.join(assurances)})")
    elif assurances:
        terms.append(assurances[0])

    if not terms:
        return "true  /* TODO: no condition/exclusion/assurance in variable_map */"
    return " || ".join(terms)


def _generate_base_property(
    rule_id: str,
    variable_map: List[Dict[str, Any]],
    actor_map: List[Dict[str, Any]],
) -> Tuple[str, List[str]]:
    """Strategy 'base': same pattern as WF-04."""
    define_lines, assumptions = _build_define_lines(variable_map, actor_map)
    rule_name = rule_id.replace("-", "")
    assertion_rhs = _build_assertion_rhs(variable_map)

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
    lines.append("")

    return "\n".join(lines), assumptions


def _generate_temporal_property(
    rule_id: str,
    variable_map: List[Dict[str, Any]],
    actor_map: List[Dict[str, Any]],
) -> Tuple[str, List[str]]:
    """Strategy 'temporal': base assertion + LTL { G(assertion); } block."""
    define_lines, assumptions = _build_define_lines(variable_map, actor_map)
    rule_name = rule_id.replace("-", "")
    assertion_rhs = _build_assertion_rhs(variable_map)

    lines = [
        "property {",
        "  define {",
    ]
    lines.extend(define_lines)
    lines.append("  }")
    lines.append("  Assertion {")
    lines.append(f"    {rule_name}: {assertion_rhs};")
    lines.append("  }")
    lines.append("  LTL {")
    lines.append(f"    G({rule_name});")
    lines.append("  }")
    lines.append("}")
    lines.append("")

    assumptions.append(
        "LTL block requires Timed Rebeca LTL model checker support — verify rmc.jar supports --ltl flag"
    )

    return "\n".join(lines), assumptions


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def _confidence(
    strategy: str,
    variable_map: List[Dict[str, Any]],
    legata_text: str,
) -> str:
    """
    Estimate confidence for a candidate artifact.

    'base'    : high when variable_map is non-empty and legata_text provides
                evidence; medium when variable_map is non-empty but no text;
                low when variable_map is empty.
    'temporal': always medium — LTL wrapping adds unverified structural assumptions.
    """
    if strategy == "temporal":
        return "medium"
    if not variable_map:
        return "low"
    if legata_text and len(legata_text.strip()) > 20:
        return "high"
    return "medium"


# ---------------------------------------------------------------------------
# Core generation logic
# ---------------------------------------------------------------------------

def run_llm_lane(
    rule_id: str,
    abstraction_summary: Dict[str, Any],
    output_dir: str,
    legata_text: str = "",
) -> Tuple[Dict[str, Any], int]:
    """
    Execute WF-06 candidate generation pipeline.

    Returns (output_dict, exit_code): exit_code 0 = success, 1 = agent failure.
    """
    # 1. Validate output_dir
    od, err = _checked_safe_path(output_dir, "output_dir")
    if err:
        return _error(f"Invalid path: {err}"), 1

    # 2. Extract abstraction inputs
    actor_map:    List[Dict[str, Any]] = abstraction_summary.get("actor_map", [])
    variable_map: List[Dict[str, Any]] = abstraction_summary.get("variable_map", [])

    if not actor_map and not variable_map:
        return _error(
            "abstraction_summary has empty actor_map and variable_map — nothing to generate"
        ), 1

    # Inject default actor when variables exist but no actors were extracted
    if not actor_map:
        actor_map = [{"legata_actor": "actor", "rebeca_class": "Actor", "rebeca_instance": "actor"}]

    # 3. Generate shared model content (same for both strategies)
    model_content = _generate_model(actor_map, variable_map)

    # 4. Create output directory
    try:
        od.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return _error(f"Cannot create output_dir '{od}': {exc}"), 1

    # 5. Generate and write both candidates
    open_assumptions: List[str] = []
    candidate_artifacts: List[Dict[str, Any]] = []

    strategies = [
        ("base",     _generate_base_property),
        ("temporal", _generate_temporal_property),
    ]

    for strategy_name, gen_fn in strategies:
        artifact_id = f"{rule_id}_llm_{strategy_name}"
        model_stem = f"{artifact_id}.rebeca"
        prop_stem  = f"{artifact_id}.property"

        prop_content, assumptions = gen_fn(rule_id, variable_map, actor_map)

        # Collect unique open_assumptions
        for a in assumptions:
            if a not in open_assumptions:
                open_assumptions.append(a)

        # Write artifacts
        try:
            model_file = od / model_stem
            prop_file  = od / prop_stem
            model_file.write_text(model_content, encoding="utf-8")
            prop_file.write_text(prop_content, encoding="utf-8")
        except Exception as exc:
            return _error(f"Failed to write {strategy_name} artifact: {exc}"), 1

        candidate_artifacts.append({
            "artifact_id":      artifact_id,
            "strategy":         strategy_name,
            "model_path":       str(model_file.resolve()),
            "property_path":    str(prop_file.resolve()),
            "model_content":    model_content,
            "property_content": prop_content,
            "mapping_path":     "llm-lane",
            "is_candidate":     True,
            "confidence":       _confidence(strategy_name, variable_map, legata_text),
            "assumptions":      assumptions,
        })

    # 6. Build contract
    contract: Dict[str, Any] = {
        "status":              "ok",
        "rule_id":             rule_id,
        "candidate_artifacts": candidate_artifacts,
        "open_assumptions":    open_assumptions,
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
        description="llm-lane-agent (WF-06): LLM-assisted candidate property generation"
    )
    parser.add_argument("--rule-id",       required=True,
                        help="Rule identifier (e.g. Rule-22)")
    parser.add_argument("--abstraction-json", required=True,
                        help="WF-03 abstraction_summary as inline JSON or @/abs/path/to/file")
    parser.add_argument("--output-dir",    required=True,
                        help="Directory to write candidate artifacts")
    parser.add_argument("--legata-text",   default="",
                        help="Raw Legata source text (enriches confidence scoring)")

    args = parser.parse_args()

    # Resolve --abstraction-json: inline JSON or @file reference
    raw = args.abstraction_json
    if raw.startswith("@"):
        file_ref = raw[1:]
        fp, err = _checked_safe_path(file_ref, "abstraction-json file")
        if err:
            print(json.dumps(_error(f"Invalid path: {err}"), indent=2))
            sys.exit(1)
        if not fp.exists():
            print(json.dumps(_error(f"abstraction-json file not found: {file_ref}"), indent=2))
            sys.exit(1)
        try:
            raw = fp.read_text(encoding="utf-8")
        except Exception as exc:
            print(json.dumps(_error(f"Cannot read abstraction JSON file: {exc}"), indent=2))
            sys.exit(1)

    try:
        abstraction_summary = json.loads(raw)
    except Exception as exc:
        print(json.dumps(_error(f"Failed to parse abstraction_summary JSON: {exc}"), indent=2))
        sys.exit(1)

    result, exit_code = run_llm_lane(
        rule_id=args.rule_id,
        abstraction_summary=abstraction_summary,
        output_dir=args.output_dir,
        legata_text=args.legata_text,
    )
    print(json.dumps(result, indent=2))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
