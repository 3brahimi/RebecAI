#!/usr/bin/env python3
"""
abstraction-agent (WF-03): Abstraction and Discretization Setup

Extracts actors and conditions from a Legata file, applies deterministic
naming conventions (PascalCase classes, camelCase statevars/defines), and
discretizes concepts to Rebeca-compatible types with bounded ranges.

Exit codes:
  0: Success — full contract written to stdout
  1: Failure — error envelope written to stdout
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Bootstrap: add skills scripts to sys.path
# ---------------------------------------------------------------------------
_SCRIPTS = Path(__file__).parent.parent / "skills" / "rebeca-tooling" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from snapshotter import extract_state_variables, extract_property_identifiers  # noqa: E402
from utils import safe_path  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# COLREG maritime actor keywords (from COLREGFallbackMapper corpus)
_MARITIME_ACTORS: List[str] = [
    "vessel", "ship", "boat", "aircraft",
    "light", "shape", "signal", "whistle",
    "visibility", "fog",
]

# Legata section labels to extract from
_SECTION_LABELS: List[str] = ["condition", "exclusion", "assurance", "assure", "exclude"]

# Patterns that indicate boolean semantics
_BOOLEAN_PATTERNS: re.Pattern = re.compile(
    r"\b(is|has|can|exhibits?|shows?|displays?|anchored|underway|"
    r"visible|present|active|enabled|required)\b",
    re.IGNORECASE,
)

# Patterns that indicate integer semantics
_INTEGER_CONCEPTS: re.Pattern = re.compile(
    r"\b(speed|range|distance|count|number|length|depth|angle|"
    r"heading|bearing|time|duration|period)\b",
    re.IGNORECASE,
)

# Fixed naming contract (never changes)
_NAMING_CONTRACT: Dict[str, str] = {
    "reactive_class_style": "PascalCase",
    "state_var_style": "camelCase",
    "instance_style": "lowerCamelCase",
    "define_alias_style": "camelCase",
    "assertion_name_style": "PascalCase",
}


# ---------------------------------------------------------------------------
# Naming conversion helpers
# ---------------------------------------------------------------------------

def _tokenize(s: str) -> List[str]:
    """Split on non-alphanumeric characters and drop empty tokens."""
    return [t for t in re.split(r"[^A-Za-z0-9]+", s) if t]


def to_pascal_case(s: str) -> str:
    """Convert any string to PascalCase."""
    return "".join(w.capitalize() for w in _tokenize(s)) or s


def to_camel_case(s: str) -> str:
    """Convert any string to camelCase."""
    words = _tokenize(s)
    if not words:
        return s
    return words[0].lower() + "".join(w.capitalize() for w in words[1:])


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _extract_legata_actors(content: str) -> List[str]:
    """Return maritime actors mentioned in the Legata content (ordered by first appearance)."""
    seen: Set[str] = set()
    found: List[str] = []
    for actor in _MARITIME_ACTORS:
        if actor.lower() in content.lower() and actor not in seen:
            seen.add(actor)
            found.append(actor)
    return found


def _extract_legata_sections(content: str) -> List[Tuple[str, str]]:
    """
    Return (source_label, text) pairs for each Legata section line.

    Handles forms like:
      condition: vessel exhibits lights
      assurance: lights comply with range >= 6
    """
    pairs: List[Tuple[str, str]] = []
    label_pattern = re.compile(
        r"^(" + "|".join(_SECTION_LABELS) + r")\s*:\s*(.+)$",
        re.IGNORECASE | re.MULTILINE,
    )
    for m in label_pattern.finditer(content):
        raw_label = m.group(1).lower()
        # Normalise assure→assurance, exclude→exclusion
        label = "assurance" if raw_label in ("assure",) else \
                "exclusion"  if raw_label in ("exclude",) else raw_label
        pairs.append((label, m.group(2).strip()))
    return pairs


def _concept_to_variable(concept: str) -> Tuple[str, str, Optional[Dict[str, int]]]:
    """
    Map a Legata concept phrase to (rebeca_name, rebeca_type, bounds_or_None).

    Type heuristic:
      - integer concept keyword present → int, bounds [0, 30]
      - boolean indicator present OR ambiguous → boolean, no bounds
    """
    if _INTEGER_CONCEPTS.search(concept):
        # Extract the integer concept word for naming
        m = _INTEGER_CONCEPTS.search(concept)
        keyword = m.group(0).lower()  # type: ignore[union-attr]
        rebeca_name = to_camel_case(keyword)
        return rebeca_name, "int", {"min": 0, "max": 30}

    # Boolean: find the most descriptive verb/adjective phrase
    words = _tokenize(concept)
    # Prefer "has<Noun>" or "is<Adjective>" patterns
    for i, w in enumerate(words):
        if w.lower() in ("has", "is", "exhibits", "shows", "displays"):
            rest = "".join(x.capitalize() for x in words[i + 1 : i + 3])
            if rest:
                return f"{w.lower()}{rest}", "boolean", None
    # Fallback: camelCase of first two content words
    content_words = [w for w in words if len(w) > 2][:2]
    name = to_camel_case(" ".join(content_words)) if content_words else to_camel_case(concept[:20])
    return name, "boolean", None


def _define_alias(rebeca_name: str, rebeca_type: str) -> str:
    """
    Produce a camelCase property `define` alias for a state variable.

    Examples:
      hasLight (bool)  → isLightOn
      lightRange (int) → lightRangeOk
      speed (int)      → speedOk
    """
    if rebeca_type == "boolean":
        # Strip leading 'has' → 'is<Noun>On'
        if rebeca_name.startswith("has"):
            noun = rebeca_name[3:]  # e.g. 'Light'
            return f"is{noun}On"
        if rebeca_name.startswith("is"):
            return rebeca_name  # already an alias
        return f"is{rebeca_name.capitalize()}"
    else:
        return f"{rebeca_name}Ok"


def _seed_from_snapshot(snapshot_path: str) -> Tuple[List[str], List[str]]:
    """
    Load state variable names and property identifiers from a WF-01 snapshot.

    Returns (state_vars, prop_ids) — both may be empty if snapshot is absent/invalid.
    Raises ValueError on JSON parse error.
    """
    try:
        snap_path = safe_path(snapshot_path)
    except SystemExit:
        raise ValueError(f"snapshot_path escapes ~: {snapshot_path}")

    if not snap_path.exists():
        return [], []

    data = json.loads(snap_path.read_text(encoding="utf-8"))
    state_vars = data.get("golden", {}).get("model", {}).get("state_variables", [])
    prop_ids = data.get("golden", {}).get("property", {}).get("identifiers", [])
    return list(state_vars), list(prop_ids)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(message: str) -> Dict[str, Any]:
    return {"status": "error", "phase": "step03", "agent": "abstraction-agent", "message": message}


def _checked_safe_path(p: str, label: str) -> Tuple[Optional[Path], Optional[str]]:
    try:
        return safe_path(p), None
    except SystemExit:
        return None, f"{label} path escapes allowed base (~): {p}"
    except Exception as exc:
        return None, f"{label} path error: {exc}"


def _validate_output(result: Dict[str, Any]) -> Optional[str]:
    schema_path = Path(__file__).parent / "abstraction-agent.schema.json"
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
# Core abstraction logic
# ---------------------------------------------------------------------------

def run_abstraction(
    rule_id: str,
    legata_path: str,
    snapshot_path: Optional[str],
    colreg_text: str,
) -> Tuple[Dict[str, Any], int]:
    """
    Execute WF-03 abstraction steps.

    Returns (output_dict, exit_code): exit_code 0 = success, 1 = failure.
    """
    # 1. Validate legata_path
    lp, err = _checked_safe_path(legata_path, "legata_path")
    if err:
        return _error(f"Invalid path: {err}"), 1

    # 2. Read Legata content
    try:
        assert lp is not None
        content = lp.read_text(encoding="utf-8") if lp.exists() else ""
    except Exception as exc:
        return _error(f"Failed to read legata file: {exc}"), 1

    # 3. Seed from snapshot (WF-01 output)
    snapshot_state_vars: List[str] = []
    snapshot_prop_ids: List[str] = []
    if snapshot_path:
        try:
            snapshot_state_vars, snapshot_prop_ids = _seed_from_snapshot(snapshot_path)
        except (ValueError, json.JSONDecodeError) as exc:
            return _error(f"Invalid snapshot JSON: {exc}"), 1

    # 4. Extract actors
    actors_from_legata = _extract_legata_actors(content)
    actors_from_colreg = _extract_legata_actors(colreg_text)
    seen_actors: Set[str] = set()
    all_actors: List[str] = []
    for a in actors_from_legata + actors_from_colreg:
        if a not in seen_actors:
            seen_actors.add(a)
            all_actors.append(a)

    actor_map = [
        {
            "legata_actor": a,
            "rebeca_class": to_pascal_case(a),
            "rebeca_instance": to_camel_case(a),
        }
        for a in all_actors
    ]

    # 5. Extract conditions from Legata sections
    sections = _extract_legata_sections(content)
    variable_map: List[Dict[str, Any]] = []
    open_assumptions: List[str] = []
    seen_names: Set[str] = set()

    for source_label, concept_text in sections:
        rebeca_name, rebeca_type, bounds = _concept_to_variable(concept_text)

        # Deduplicate: append numeric suffix if name already taken
        base_name = rebeca_name
        counter = 1
        while rebeca_name in seen_names:
            rebeca_name = f"{base_name}{counter}"
            counter += 1
        seen_names.add(rebeca_name)

        alias = _define_alias(rebeca_name, rebeca_type)
        entry: Dict[str, Any] = {
            "legata_concept": concept_text,
            "rebeca_name": rebeca_name,
            "rebeca_type": rebeca_type,
            "define_alias": alias,
            "source": source_label,
        }
        if bounds is not None:
            entry["bounds"] = bounds
            open_assumptions.append(
                f"Default integer bounds [{bounds['min']}, {bounds['max']}] "
                f"applied to '{rebeca_name}' — refine manually if domain requires different range"
            )
        variable_map.append(entry)

    # 6. Seed additional state vars from snapshot not yet in variable_map
    existing_names = {v["rebeca_name"] for v in variable_map}
    for sv in snapshot_state_vars:
        if sv in existing_names:
            continue
        _, sv_type, sv_bounds = _concept_to_variable(sv)
        entry = {
            "legata_concept": f"[from snapshot] {sv}",
            "rebeca_name": sv,
            "rebeca_type": sv_type,
            "define_alias": _define_alias(sv, sv_type),
            "source": "inferred",
        }
        if sv_bounds is not None:
            entry["bounds"] = sv_bounds
            open_assumptions.append(
                f"Snapshot variable '{sv}' type inferred as int [0, 30] — verify"
            )
        variable_map.append(entry)
        existing_names.add(sv)

    # 7. Guard: at least one symbol must be produced
    if not actor_map and not variable_map:
        return _error(
            "Abstraction produced no symbols: legata file has no recognisable "
            "actors or condition/exclusion/assurance sections"
        ), 1

    # 8. Build and validate contract
    contract: Dict[str, Any] = {
        "status": "ok",
        "rule_id": rule_id,
        "abstraction_summary": {
            "naming_contract": _NAMING_CONTRACT,
            "actor_map": actor_map,
            "variable_map": variable_map,
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
        description="abstraction-agent (WF-03): discretize Legata to Rebeca symbol namespace"
    )
    parser.add_argument("--rule-id",       required=True, help="Rule identifier (e.g. Rule-22)")
    parser.add_argument("--legata-path",   required=True, help="Path to .legata source file")
    parser.add_argument("--snapshot-path", default=None,  help="WF-01 snapshot JSON (optional)")
    parser.add_argument("--colreg-text",   default="",    help="Supplementary COLREG text (optional)")

    args = parser.parse_args()

    result, exit_code = run_abstraction(
        rule_id=args.rule_id,
        legata_path=args.legata_path,
        snapshot_path=args.snapshot_path,
        colreg_text=args.colreg_text,
    )
    print(json.dumps(result, indent=2))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
