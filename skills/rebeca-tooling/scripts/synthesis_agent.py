#!/usr/bin/env python3
"""
synthesis-agent (WF-05): Property Synthesis

Positioned between WF-04 (mapping-agent) and WF-06 (verification-agent).
Takes the WF-04 model+property artifacts and synthesizes a refined candidate
using the MutationEngine's property-side transformation strategies.

Architecture:
  Agent layer (here): decides WHICH formulation to select and why
  Skill layer (MutationEngine): applies the transformation rules

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
# Bootstrap: scripts dir on sys.path for hyphen-named modules
# ---------------------------------------------------------------------------
_SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(_SCRIPTS))

_mutation_mod = importlib.import_module("mutation-engine")
MutationEngine = _mutation_mod.MutationEngine

from utils import safe_path  # noqa: E402


# ---------------------------------------------------------------------------
# Property-side synthesis strategies (ordered: most conservative first)
# These use MutationEngine to generate variants, not to kill mutants.
# ---------------------------------------------------------------------------
_PROPERTY_STRATEGIES: Tuple[str, ...] = (
    "comparison_value_mutation",
    "boolean_predicate_negation",
    "logical_swap",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(message: str) -> Dict[str, Any]:
    return {
        "status": "error", "phase": "step05",
        "agent": "synthesis-agent", "message": message,
    }


def _checked_safe_path(p: str, label: str) -> Tuple[Optional[Path], Optional[str]]:
    try:
        return safe_path(p), None
    except SystemExit:
        return None, f"{label} path escapes allowed base (~): {p}"
    except Exception as exc:
        return None, f"{label} path error: {exc}"


def _validate_output(result: Dict[str, Any]) -> Optional[str]:
    schema_path = Path(__file__).parent.parent / "schemas" / "synthesis-agent.schema.json"
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
# Synthesis selection heuristic
# ---------------------------------------------------------------------------

def _select_best(
    base_content: str,
    variants: List[Dict[str, Any]],
) -> Tuple[str, str, str]:
    """
    Select the best property variant.

    Heuristic: prefer the variant with the greatest absolute difference from
    the base (more terms changed = richer formulation). Fall back to base if
    no variants differ meaningfully.

    Returns (selected_content, selected_strategy, rationale).
    """
    best_content  = base_content
    best_strategy = "identity"
    best_delta    = 0

    for v in variants:
        c = v["mutated_content"]
        if c == base_content:
            continue
        # Simple diff metric: character-level edit distance proxy
        delta = sum(a != b for a, b in zip(c, base_content))
        delta += abs(len(c) - len(base_content))
        if delta > best_delta:
            best_delta    = delta
            best_content  = c
            best_strategy = v["strategy"]

    rationale = (
        f"Selected strategy '{best_strategy}' with edit-delta={best_delta} "
        f"from {len(variants)} candidate(s) + identity."
    )
    return best_content, best_strategy, rationale


# ---------------------------------------------------------------------------
# Core synthesis logic
# ---------------------------------------------------------------------------

def run_synthesis(
    rule_id: str,
    model_path: str,
    property_path: str,
    output_dir: str,
) -> Tuple[Dict[str, Any], int]:
    """Execute WF-05 synthesis pipeline. Returns (contract, exit_code)."""

    # 1. Validate paths
    mp, err = _checked_safe_path(model_path, "model_path")
    if err:
        return _error(f"Invalid path: {err}"), 1

    pp, err = _checked_safe_path(property_path, "property_path")
    if err:
        return _error(f"Invalid path: {err}"), 1

    od, err = _checked_safe_path(output_dir, "output_dir")
    if err:
        return _error(f"Invalid path: {err}"), 1

    if not mp.exists():
        return _error(f"model_path not found: {model_path}"), 1
    if not pp.exists():
        return _error(f"property_path not found: {property_path}"), 1

    # 2. Read base artifacts
    model_content    = mp.read_text(encoding="utf-8")
    property_content = pp.read_text(encoding="utf-8")

    # 3. Generate property variants via MutationEngine (skill layer)
    try:
        engine = MutationEngine()
    except Exception as exc:
        return _error(f"MutationEngine instantiation failed: {exc}"), 1

    all_variants: List[Dict[str, Any]] = []
    strategies_tried: List[str] = ["identity"]

    for strategy in _PROPERTY_STRATEGIES:
        mutant_fn = getattr(engine, strategy, None)
        if mutant_fn is None:
            continue
        try:
            for mut in mutant_fn(property_content, rule_id):
                if mut.mutated_content != property_content:
                    all_variants.append({
                        "strategy":        strategy,
                        "mutated_content": mut.mutated_content,
                        "description":     mut.description,
                    })
            strategies_tried.append(strategy)
        except Exception:
            pass  # strategy not applicable — skip

    # 4. Select best synthesis candidate
    selected_property, selected_strategy, rationale = _select_best(
        property_content, all_variants
    )

    # 5. Write selected artifacts to output_dir
    try:
        od.mkdir(parents=True, exist_ok=True)
        out_model = od / f"{rule_id}_synthesized.rebeca"
        out_prop  = od / f"{rule_id}_synthesized.property"
        out_model.write_text(model_content, encoding="utf-8")
        out_prop.write_text(selected_property, encoding="utf-8")
    except Exception as exc:
        return _error(f"Failed to write synthesized artifacts: {exc}"), 1

    # 6. Build contract
    contract: Dict[str, Any] = {
        "status":                  "ok",
        "rule_id":                 rule_id,
        "selected_model_path":     str(out_model.resolve()),
        "selected_property_path":  str(out_prop.resolve()),
        "synthesis_summary": {
            "strategies_tried":   strategies_tried,
            "variants_generated": len(all_variants),
            "selected_strategy":  selected_strategy,
            "rationale":          rationale,
            "property_changed":   selected_property != property_content,
        },
        "open_assumptions": [
            "Synthesis selects by edit-delta heuristic — WF-06 verification "
            "confirms whether the synthesized property is formally correct.",
        ],
    }

    if schema_err := _validate_output(contract):
        return _error(schema_err), 1

    return contract, 0


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="synthesis-agent (WF-05): synthesize refined property from WF-04 artifacts"
    )
    parser.add_argument("--rule-id",       required=True, help="Rule identifier (e.g. Rule-22)")
    parser.add_argument("--model-path",    required=True, help="Path to WF-04 .rebeca model")
    parser.add_argument("--property-path", required=True, help="Path to WF-04 .property file")
    parser.add_argument("--output-dir",    required=True, help="Directory for synthesized artifacts")

    args = parser.parse_args()

    result, exit_code = run_synthesis(
        rule_id=args.rule_id,
        model_path=args.model_path,
        property_path=args.property_path,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
