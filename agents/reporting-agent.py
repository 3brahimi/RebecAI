#!/usr/bin/env python3
"""
reporting-agent (WF-08): Aggregate Scoring Report Generation

Wraps ReportGenerator (generate_report.py) to consume per-rule scorecards
assembled by the coordinator, finalize aggregate metrics, and write
report.json + report.md to the designated output directory.

NOTE: Scoring (RubricScorer.score_rule) runs BEFORE this agent — the
coordinator passes finalized scorecards in. This agent only aggregates
and formats. ReportGenerator and RubricScorer are NOT exported from
skills/__init__.py; imported directly from generate_report.py.

Exit codes:
  0: Success — contract written to stdout
  1: Failure — error envelope written to stdout
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Bootstrap: add skills scripts to sys.path
# ---------------------------------------------------------------------------
_SCRIPTS = Path(__file__).parent.parent / "skills" / "rebeca-tooling" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from utils import safe_path          # noqa: E402
from generate_report import ReportGenerator  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(message: str) -> Dict[str, Any]:
    """Canonical Error Envelope for WF-08."""
    return {
        "status":  "error",
        "phase":   "step08",
        "agent":   "reporting-agent",
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


def _parse_scorecards(raw: Any) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """
    Resolve scorecards from:
      - a list (already parsed by argparse via JSON)
      - a string that is either inline JSON or '@/abs/path/to/file'

    Returns (list_of_scorecards, error_string).
    """
    if isinstance(raw, list):
        return raw, None

    if not isinstance(raw, str):
        return None, f"scorecards must be a JSON array or string, got {type(raw).__name__}"

    # File reference: '@/path/to/file'
    if raw.startswith("@"):
        file_ref = raw[1:]
        fp, err = _checked_safe_path(file_ref, "scorecards file")
        if err:
            return None, err
        if not fp.exists():
            return None, f"scorecard file not found: {file_ref}"
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as exc:
            return None, f"Failed to parse scorecard file: {exc}"
        if not isinstance(data, list):
            return None, "Scorecard file must contain a JSON array"
        return data, None

    # Inline JSON string
    try:
        data = json.loads(raw)
    except Exception as exc:
        return None, f"Failed to parse inline scorecards JSON: {exc}"
    if not isinstance(data, list):
        return None, "Inline scorecards must be a JSON array"
    return data, None


def _validate_scorecards(scorecards: List[Dict[str, Any]]) -> Optional[str]:
    """Ensure each scorecard has the minimum fields ReportGenerator.add_scorecard() reads."""
    required = {"rule_id", "score_total", "status"}
    for i, sc in enumerate(scorecards):
        missing = required - sc.keys()
        if missing:
            return f"Scorecard[{i}] missing required fields: {sorted(missing)}"
    return None


def _extract_summary(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """Pull aggregate fields from ReportGenerator.report_data into the summary contract."""
    return {
        "total_rules":          report_data.get("total_rules", 0),
        "rules_passed":         report_data.get("rules_passed", 0),
        "rules_failed":         report_data.get("rules_failed", 0),
        "score_mean":           report_data.get("score_mean", 0.0),
        "score_min":            report_data.get("score_min", 0),
        "score_max":            report_data.get("score_max", 0),
        "success_rate":         report_data.get("success_rate", 0.0),
        "fallback_usage_count": report_data.get("fallback_usage_count", 0),
        "blocked_rules_count":  report_data.get("blocked_rules_count", 0),
    }


def _validate_output(result: Dict[str, Any]) -> Optional[str]:
    """Validate result against the output sub-schema."""
    schema_path = Path(__file__).parent / "reporting-agent.schema.json"
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
# Core reporting logic
# ---------------------------------------------------------------------------

def run_reporting(
    scorecards_raw: Any,
    output_dir: str,
) -> Tuple[Dict[str, Any], int]:
    """
    Execute WF-08 reporting pipeline.

    Returns (output_dict, exit_code): exit_code 0 = success, 1 = agent failure.
    """
    # 1. Validate output_dir path
    od, err = _checked_safe_path(output_dir, "output_dir")
    if err:
        return _error(f"Invalid path: {err}"), 1

    # 2. Parse and validate scorecards
    scorecards, err = _parse_scorecards(scorecards_raw)
    if err:
        return _error(f"Scorecard parse error: {err}"), 1

    if not scorecards:
        return _error("scorecards array is empty — nothing to report"), 1

    err = _validate_scorecards(scorecards)
    if err:
        return _error(f"Scorecard integrity error: {err}"), 1

    # 3. Feed scorecards to ReportGenerator
    try:
        generator = ReportGenerator()
    except Exception as exc:
        return _error(f"ReportGenerator instantiation failed: {exc}"), 1

    for sc in scorecards:
        try:
            generator.add_scorecard(sc)
        except Exception as exc:
            return _error(f"add_scorecard failed for rule_id={sc.get('rule_id', '?')}: {exc}"), 1

    # 4. Finalize aggregate metrics
    try:
        generator.finalize()
    except Exception as exc:
        return _error(f"ReportGenerator.finalize() failed: {exc}"), 1

    # 5. Write report.json and report.md via safe_path
    try:
        od.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return _error(f"Cannot create output_dir '{od}': {exc}"), 1

    report_path = od / "report.json"
    report_md_path = od / "report.md"

    try:
        report_path.write_text(generator.to_json(), encoding="utf-8")
    except Exception as exc:
        return _error(f"Failed to write report.json: {exc}"), 1

    try:
        report_md_path.write_text(generator.to_markdown(), encoding="utf-8")
    except Exception as exc:
        return _error(f"Failed to write report.md: {exc}"), 1

    # 6. Build contract
    contract: Dict[str, Any] = {
        "status":         "ok",
        "report_path":    str(report_path),
        "report_md_path": str(report_md_path),
        "summary":        _extract_summary(generator.report_data),
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
        description="reporting-agent (WF-08): aggregate scoring report via ReportGenerator"
    )
    parser.add_argument(
        "--scorecards",
        required=True,
        help=(
            "Per-rule scorecards. Accepts: "
            "(1) inline JSON array string, "
            "(2) @/abs/path/to/scorecards.json"
        ),
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write report.json and report.md",
    )

    args = parser.parse_args()

    # Try to parse --scorecards as JSON first (inline array); fall back to raw string
    scorecards_raw: Any = args.scorecards
    try:
        parsed = json.loads(args.scorecards)
        if isinstance(parsed, list):
            scorecards_raw = parsed
    except (json.JSONDecodeError, ValueError):
        pass  # keep as string (file reference or will fail in _parse_scorecards)

    result, exit_code = run_reporting(
        scorecards_raw=scorecards_raw,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
