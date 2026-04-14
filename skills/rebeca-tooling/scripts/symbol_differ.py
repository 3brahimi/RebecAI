#!/usr/bin/env python3
"""State-aware hallucination detection for Rebeca model/property artifacts."""

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from utils import safe_path


_IDENTIFIER_PATTERN = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_KEYWORDS = {
    "reactiveclass", "statevars", "msgsrv", "main", "if", "else", "while",
    "for", "return", "int", "boolean", "byte", "short", "long", "float",
    "double", "char", "String", "true", "false", "property", "define",
    "Assertion", "LTL", "G", "F", "X", "U", "Error", "line", "column",
}


@dataclass
class HallucinationResult:
    rule_id: str
    is_hallucination: bool
    hallucination_type: str
    offending_symbols: List[str]
    rmc_error_trace: str
    tier1_dead_code_symbols: List[str]
    tier2_reference_symbols: List[str]


def extract_state_variables(model_content: str) -> Set[str]:
    names: Set[str] = set()
    for block in re.finditer(r"\bstatevars\s*\{([^}]*)\}", model_content, re.DOTALL):
        text = block.group(1)
        for stmt in text.split(";"):
            stmt = stmt.strip()
            if not stmt:
                continue
            m = re.match(r"[A-Za-z_][A-Za-z0-9_<>\[\]]*\s+(.+)", stmt)
            if not m:
                continue
            for raw_name in m.group(1).split(","):
                name = raw_name.strip().split("=")[0].strip()
                if name and _IDENTIFIER_PATTERN.fullmatch(name):
                    names.add(name)
    return names


def extract_model_logic_identifiers(model_content: str) -> Set[str]:
    refs: Set[str] = set()
    for body_match in re.finditer(
        r"(?:\bmsgsrv\s+\w+\s*\([^)]*\)\s*\{|\b\w+\s*\([^)]*\)\s*\{)([^}]*)\}",
        model_content,
        re.DOTALL,
    ):
        for token in _IDENTIFIER_PATTERN.findall(body_match.group(1)):
            if token not in _KEYWORDS:
                refs.add(token)
    return refs


def extract_property_identifiers(property_content: str) -> Set[str]:
    ids: Set[str] = set()
    for block in re.finditer(r"\b(?:define|Assertion)\s*\{([^}]*)\}", property_content, re.DOTALL):
        for token in _IDENTIFIER_PATTERN.findall(block.group(1)):
            if token not in _KEYWORDS:
                ids.add(token)
    for actor_var in re.finditer(r"\b\w+\.(\w+)\b", property_content):
        ids.add(actor_var.group(1))
    return ids


def extract_stderr_identifiers(stderr_text: str) -> Set[str]:
    ids = {t for t in _IDENTIFIER_PATTERN.findall(stderr_text) if t not in _KEYWORDS}
    # Filter obvious file/path fragments
    return {t for t in ids if "/" not in t and "\\" not in t and len(t) > 1}


def detect_hallucinations(
    snapshot_path: str,
    current_model: str,
    current_property: str,
    rmc_exit_code: Optional[int] = None,
    rmc_stderr_log: Optional[str] = None,
) -> HallucinationResult:
    """Run tier-1 and tier-2 hallucination checks against a golden snapshot."""
    snap_path = safe_path(snapshot_path)
    model_path = safe_path(current_model)
    prop_path = safe_path(current_property)

    if not snap_path.exists() or not model_path.exists() or not prop_path.exists():
        missing = []
        if not snap_path.exists():
            missing.append(snapshot_path)
        if not model_path.exists():
            missing.append(current_model)
        if not prop_path.exists():
            missing.append(current_property)
        raise FileNotFoundError(f"Missing input file(s): {', '.join(missing)}")

    snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
    rule_id = snapshot.get("rule_id", "unknown")

    golden_state_vars = set(snapshot.get("golden", {}).get("model", {}).get("state_variables", []))

    model_content = model_path.read_text(encoding="utf-8")
    property_content = prop_path.read_text(encoding="utf-8")

    current_state_vars = extract_state_variables(model_content)
    model_logic_refs = extract_model_logic_identifiers(model_content)
    property_ids = extract_property_identifiers(property_content)

    # Tier 1: Dead-Code Hallucination (added state vars never referenced)
    added_state_vars = current_state_vars - golden_state_vars
    referenced = model_logic_refs | property_ids
    dead_code_symbols = sorted(v for v in added_state_vars if v not in referenced)

    # Tier 2: Reference Hallucination classification when parse fails (exit code 5)
    stderr_text = ""
    if rmc_stderr_log:
        err_path = safe_path(rmc_stderr_log)
        if err_path.exists():
            stderr_text = err_path.read_text(encoding="utf-8", errors="replace")
    stderr_ids = extract_stderr_identifiers(stderr_text)

    missing_property_refs = sorted(v for v in property_ids if v in added_state_vars and v not in current_state_vars)
    # More robust: property refs not present in model state, regardless of whether they are added
    strict_missing_refs = sorted(v for v in property_ids if v not in current_state_vars)

    reference_symbols: List[str] = []
    if rmc_exit_code == 5:
        if strict_missing_refs:
            if stderr_ids:
                matched = sorted(set(strict_missing_refs) & stderr_ids)
                reference_symbols = matched if matched else strict_missing_refs
            else:
                reference_symbols = strict_missing_refs

    if dead_code_symbols:
        hallucination_type = "dead_code"
        offending = dead_code_symbols
        is_hallucination = True
    elif reference_symbols:
        hallucination_type = "reference"
        offending = reference_symbols
        is_hallucination = True
    elif rmc_exit_code == 5:
        hallucination_type = "syntax"
        offending = sorted(stderr_ids)[:20]
        is_hallucination = False
    else:
        hallucination_type = "none"
        offending = []
        is_hallucination = False

    return HallucinationResult(
        rule_id=rule_id,
        is_hallucination=is_hallucination,
        hallucination_type=hallucination_type,
        offending_symbols=offending,
        rmc_error_trace=stderr_text,
        tier1_dead_code_symbols=dead_code_symbols,
        tier2_reference_symbols=reference_symbols,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit Rebeca model/property hallucinations using symbol diffing"
    )
    parser.add_argument("--snapshot", required=True, help="Path to golden snapshot JSON")
    parser.add_argument("--model", required=True, help="Path to current .rebeca file")
    parser.add_argument("--property", required=True, help="Path to current .property file")
    parser.add_argument("--rmc-exit-code", type=int, default=None, help="RMC exit code for current run")
    parser.add_argument("--rmc-stderr-log", default=None, help="Path to rmc_stderr.log")
    parser.add_argument("--output-json", action="store_true", help="Print JSON result")
    args = parser.parse_args()

    try:
        result = detect_hallucinations(
            snapshot_path=args.snapshot,
            current_model=args.model,
            current_property=args.property,
            rmc_exit_code=args.rmc_exit_code,
            rmc_stderr_log=args.rmc_stderr_log,
        )
        payload = asdict(result)

        if args.output_json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Rule: {payload['rule_id']}")
            print(f"is_hallucination: {payload['is_hallucination']}")
            print(f"hallucination_type: {payload['hallucination_type']}")
            print(f"offending_symbols: {', '.join(payload['offending_symbols']) or '-'}")

        sys.exit(1 if payload["is_hallucination"] else 0)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
