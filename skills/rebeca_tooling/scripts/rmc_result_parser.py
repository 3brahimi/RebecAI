#!/usr/bin/env python3
"""Parse RMC/model.out exported result artifacts into normalized outcomes."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict

from utils import safe_path

_NEGATIVE_PATTERNS = (
    "counterexample",
    "not satisfied",
    "property violated",
    "violated",
    "fail",
    "false",
    "unsafe",
)

_POSITIVE_PATTERNS = (
    "property is satisfied",
    "satisfied",
    "verified",
    "pass",
    "true",
    "safe",
)


def _normalise_status(text: str) -> str:
    """Map free-text verdict content to semantic outcome labels."""
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    if not normalized:
        return "unknown"

    if any(pattern in normalized for pattern in _NEGATIVE_PATTERNS):
        return "cex"
    if any(pattern in normalized for pattern in _POSITIVE_PATTERNS):
        return "satisfied"
    return "unknown"


def _extract_xml_signal(root: ET.Element) -> str:
    """Extract semantic signal from XML tags/attributes/text."""
    candidates = []

    for elem in root.iter():
        tag = elem.tag.lower() if isinstance(elem.tag, str) else ""
        if elem.text:
            candidates.append(f"{tag}:{elem.text}")

        for key, value in elem.attrib.items():
            key_lower = key.lower()
            value_lower = str(value).lower()

            if key_lower in {"status", "result", "verdict", "outcome"}:
                candidates.append(value_lower)
            elif key_lower in {"satisfied", "is_satisfied", "holds"}:
                if value_lower in {"true", "1", "yes"}:
                    return "satisfied"
                if value_lower in {"false", "0", "no"}:
                    return "cex"
            else:
                candidates.append(f"{key_lower}:{value_lower}")

    combined = "\n".join(candidates)
    return _normalise_status(combined)


def parse_rmc_result_file(result_path: str) -> Dict[str, Any]:
    """Parse model.out/RMC exported result artifact and normalize outcome."""
    try:
        path = safe_path(result_path)
    except SystemExit:
        return {
            "path": result_path,
            "exists": False,
            "parsed": False,
            "format": "unknown",
            "outcome": "unknown",
            "error": f"Invalid result path: {result_path}",
        }

    result: Dict[str, Any] = {
        "path": str(path),
        "exists": path.exists() and path.is_file(),
        "parsed": False,
        "format": "unknown",
        "outcome": "unknown",
        "error": None,
    }

    if not result["exists"]:
        result["error"] = f"Result file not found: {path}"
        return result

    text = ""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        result["error"] = str(exc)
        return result

    try:
        tree = ET.parse(str(path))
        root = tree.getroot()
        result["format"] = "xml"
        result["parsed"] = True
        result["outcome"] = _extract_xml_signal(root)
        return result
    except ET.ParseError:
        pass
    except Exception as exc:
        result["error"] = str(exc)
        return result

    result["format"] = "text"
    result["parsed"] = True
    result["outcome"] = _normalise_status(text)
    return result
