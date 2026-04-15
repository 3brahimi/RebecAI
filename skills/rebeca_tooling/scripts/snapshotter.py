#!/usr/bin/env python3
"""Golden snapshot manager for Rebeca hallucination detection."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

from utils import safe_path


_IDENTIFIER_PATTERN = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_KEYWORDS = {
    "reactiveclass", "statevars", "msgsrv", "main", "if", "else", "while",
    "for", "return", "int", "boolean", "byte", "short", "long", "float",
    "double", "char", "String", "true", "false", "property", "define",
    "Assertion", "LTL", "G", "F", "X", "U",
}


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def extract_state_variables(model_content: str) -> List[str]:
    """Extract state variable names from `statevars { ... }` blocks."""
    names: Set[str] = set()
    for block in re.finditer(r"\bstatevars\s*\{([^}]*)\}", model_content, re.DOTALL):
        text = block.group(1)
        for stmt in text.split(";"):
            stmt = stmt.strip()
            if not stmt:
                continue
            # Handles forms like: int a, b  OR  boolean hasLight
            m = re.match(r"[A-Za-z_][A-Za-z0-9_<>\[\]]*\s+(.+)", stmt)
            if not m:
                continue
            rhs = m.group(1)
            for raw_name in rhs.split(","):
                name = raw_name.strip().split("=")[0].strip()
                if name and _IDENTIFIER_PATTERN.fullmatch(name):
                    names.add(name)
    return sorted(names)


def extract_model_references(model_content: str) -> List[str]:
    """Extract identifier references from constructor/msgsrv bodies."""
    refs: Set[str] = set()
    for body_match in re.finditer(
        r"(?:\bmsgsrv\s+\w+\s*\([^)]*\)\s*\{|\b\w+\s*\([^)]*\)\s*\{)([^}]*)\}",
        model_content,
        re.DOTALL,
    ):
        body = body_match.group(1)
        for token in _IDENTIFIER_PATTERN.findall(body):
            if token not in _KEYWORDS:
                refs.add(token)
    return sorted(refs)


def extract_property_identifiers(property_content: str) -> List[str]:
    """Extract identifiers used in define/assertion expressions."""
    ids: Set[str] = set()

    for block in re.finditer(r"\bdefine\s*\{([^}]*)\}", property_content, re.DOTALL):
        for token in _IDENTIFIER_PATTERN.findall(block.group(1)):
            if token not in _KEYWORDS:
                ids.add(token)

    for block in re.finditer(r"\bAssertion\s*\{([^}]*)\}", property_content, re.DOTALL):
        for token in _IDENTIFIER_PATTERN.findall(block.group(1)):
            if token not in _KEYWORDS:
                ids.add(token)

    for actor_var in re.finditer(r"\b\w+\.(\w+)\b", property_content):
        ids.add(actor_var.group(1))

    return sorted(ids)


def capture_snapshot(model_file: str, property_file: str, rule_id: str) -> Dict[str, Any]:
    """Build a full-content golden snapshot from model and property files."""
    model_path = safe_path(model_file)
    property_path = safe_path(property_file)

    if not model_path.exists() or not property_path.exists():
        missing = []
        if not model_path.exists():
            missing.append(model_file)
        if not property_path.exists():
            missing.append(property_file)
        raise FileNotFoundError(f"Missing input file(s): {', '.join(missing)}")

    model_content = model_path.read_text(encoding="utf-8")
    property_content = property_path.read_text(encoding="utf-8")

    return {
        "rule_id": rule_id,
        "golden": {
            "model": {
                "path": str(model_path),
                "sha256": _sha256(model_content),
                "content": model_content,
                "state_variables": extract_state_variables(model_content),
                "model_references": extract_model_references(model_content),
            },
            "property": {
                "path": str(property_path),
                "sha256": _sha256(property_content),
                "content": property_content,
                "identifiers": extract_property_identifiers(property_content),
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture a golden snapshot for Rebeca hallucination detection"
    )
    parser.add_argument("--rule-id", required=True, help="Rule identifier")
    parser.add_argument("--model", required=True, help="Path to golden .rebeca file")
    parser.add_argument("--property", required=True, help="Path to golden .property file")
    parser.add_argument("--output", required=True, help="Path to output snapshot JSON")
    parser.add_argument("--output-json", action="store_true", help="Print snapshot JSON")
    args = parser.parse_args()

    try:
        snapshot = capture_snapshot(
            model_file=args.model,
            property_file=args.property,
            rule_id=args.rule_id,
        )
        out_path = safe_path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

        if args.output_json:
            print(json.dumps(snapshot, indent=2))
        else:
            print(f"Golden snapshot captured: {out_path}")
            print(f"Rule: {snapshot['rule_id']}")
            print(f"State vars: {len(snapshot['golden']['model']['state_variables'])}")
            print(f"Property identifiers: {len(snapshot['golden']['property']['identifiers'])}")
        sys.exit(0)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
