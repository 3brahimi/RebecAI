import json
import shutil
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
#!/usr/bin/env python3
"""
packaging-agent (WF-07): Artifact Collection, Manifest Generation, Installation Report

Collects pipeline artifacts (model, property, RMC logs, snapshot), copies them
to a structured destination directory, and emits a manifest with per-artifact
installation status.

NOTE: Does NOT use install_artifacts.py — that tool installs the RebecAI
framework itself (agents/skills → ~/.claude/). This agent packages rule-specific
pipeline outputs for downstream consumption.

Exit codes:
  0: Success — contract written to stdout
  1: Failure — error envelope written to stdout
"""

import sys
from .utils import safe_path  # noqa: E402



# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SUBDIRS: Dict[str, str] = {
    "model":    "model",
    "property": "property",
    "log":      "logs",
    "snapshot": "snapshot",
    "other":    "other",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(message: str) -> Dict[str, Any]:
    """Canonical Error Envelope for WF-07."""
    return {
        "status":  "error",
        "phase":   "step07",
        "agent":   "packaging-agent",
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


def _artifact_entry(
    artifact_id: str,
    source_path: str,
    dest_path: Optional[str],
    artifact_type: str,
    status: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "artifact_id":   artifact_id,
        "source_path":   source_path,
        "dest_path":     dest_path,
        "artifact_type": artifact_type,
        "status":        status,
        "reason":        reason,
    }


def _copy_artifact(
    src: Path,
    dest_dir: Path,
    dry_run: bool,
) -> Tuple[Optional[str], str, Optional[str]]:
    """
    Copy src to dest_dir / src.name.

    Returns (dest_path_str, status, reason).
    """
    dest = dest_dir / src.name
    if dry_run:
        return str(dest), "installed", None
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return str(dest), "installed", None
    except Exception as exc:
        return None, "failed", str(exc)


def _validate_output(result: Dict[str, Any]) -> Optional[str]:
    """Validate result against the output sub-schema."""
    schema_path = Path(__file__).parent / "packaging-agent.schema.json"
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
# Core packaging logic
# ---------------------------------------------------------------------------

def run_packaging(
    rule_id: str,
    model_path: str,
    property_path: str,
    rmc_output_dir: str,
    dest_dir: str,
    snapshot_path: str = "",
    dry_run: bool = False,
) -> Tuple[Dict[str, Any], int]:
    """
    Execute WF-07 packaging pipeline.

    Returns (output_dict, exit_code): exit_code 0 = success, 1 = agent failure.
    Individual artifact copy failures produce 'failed' entries — not an error envelope.
    """
    # 1. Validate required paths
    mp, err = _checked_safe_path(model_path, "model_path")
    if err:
        return _error(f"Invalid path: {err}"), 1

    pp, err = _checked_safe_path(property_path, "property_path")
    if err:
        return _error(f"Invalid path: {err}"), 1

    rod, err = _checked_safe_path(rmc_output_dir, "rmc_output_dir")
    if err:
        return _error(f"Invalid path: {err}"), 1

    dd, err = _checked_safe_path(dest_dir, "dest_dir")
    if err:
        return _error(f"Invalid path: {err}"), 1

    # Validate optional snapshot path only if provided
    sp: Optional[Path] = None
    if snapshot_path:
        sp, err = _checked_safe_path(snapshot_path, "snapshot_path")
        if err:
            return _error(f"Invalid path: {err}"), 1

    # 2. Create dest root (rule-scoped subdirectory)
    rule_dest = dd / rule_id
    try:
        if not dry_run:
            rule_dest.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return _error(f"Cannot create dest_dir '{rule_dest}': {exc}"), 1

    report: List[Dict[str, Any]] = []
    generated_files: List[str] = []

    # 3. Package model
    if mp.exists():
        sub = rule_dest / _SUBDIRS["model"]
        dest_str, status, reason = _copy_artifact(mp, sub, dry_run)
        report.append(_artifact_entry(
            f"{rule_id}_model", str(mp), dest_str, "model", status, reason
        ))
        if dest_str and status == "installed":
            generated_files.append(dest_str)
    else:
        report.append(_artifact_entry(
            f"{rule_id}_model", str(mp), None, "model", "skipped",
            "source file does not exist"
        ))

    # 4. Package property
    if pp.exists():
        sub = rule_dest / _SUBDIRS["property"]
        dest_str, status, reason = _copy_artifact(pp, sub, dry_run)
        report.append(_artifact_entry(
            f"{rule_id}_property", str(pp), dest_str, "property", status, reason
        ))
        if dest_str and status == "installed":
            generated_files.append(dest_str)
    else:
        report.append(_artifact_entry(
            f"{rule_id}_property", str(pp), None, "property", "skipped",
            "source file does not exist"
        ))

    # 5. Package RMC logs — all *.log files from rmc_output_dir
    if rod.exists():
        log_files = sorted(rod.glob("*.log"))
        log_sub = rule_dest / _SUBDIRS["log"]
        for log_file in log_files:
            dest_str, status, reason = _copy_artifact(log_file, log_sub, dry_run)
            artifact_id = f"{rule_id}_log_{log_file.stem}"
            report.append(_artifact_entry(
                artifact_id, str(log_file), dest_str, "log", status, reason
            ))
            if dest_str and status == "installed":
                generated_files.append(dest_str)
        if not log_files:
            report.append(_artifact_entry(
                f"{rule_id}_logs", str(rod), None, "log", "skipped",
                "no *.log files found in rmc_output_dir"
            ))
    else:
        report.append(_artifact_entry(
            f"{rule_id}_logs", str(rod), None, "log", "skipped",
            "rmc_output_dir does not exist"
        ))

    # 6. Package snapshot (optional)
    if sp is not None:
        if sp.exists():
            sub = rule_dest / _SUBDIRS["snapshot"]
            dest_str, status, reason = _copy_artifact(sp, sub, dry_run)
            report.append(_artifact_entry(
                f"{rule_id}_snapshot", str(sp), dest_str, "snapshot", status, reason
            ))
            if dest_str and status == "installed":
                generated_files.append(dest_str)
        else:
            report.append(_artifact_entry(
                f"{rule_id}_snapshot", str(sp), None, "snapshot", "skipped",
                "source file does not exist"
            ))

    # 7. Build contract
    contract: Dict[str, Any] = {
        "status":              "ok",
        "rule_id":             rule_id,
        "dest_dir":            str(rule_dest),
        "dry_run":             dry_run,
        "generated_files":     generated_files,
        "installation_report": report,
    }

    # 8. Validate output schema
    if schema_err := _validate_output(contract):
        return _error(schema_err), 1

    return contract, 0


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="packaging-agent (WF-07): collect artifacts and emit installation manifest"
    )
    parser.add_argument("--rule-id",        required=True, help="Rule identifier (e.g. Rule-22)")
    parser.add_argument("--model-path",     required=True, help="Path to .rebeca model file (from WF-04)")
    parser.add_argument("--property-path",  required=True, help="Path to .property file (from WF-04)")
    parser.add_argument("--rmc-output-dir", required=True, help="RMC output directory (from WF-05)")
    parser.add_argument("--dest-dir",       required=True, help="Destination directory for packaged artifacts")
    parser.add_argument("--snapshot-path",  default="",   help="Optional WF-01 snapshot file to include")
    parser.add_argument("--dry-run",        action="store_true", help="Compute manifest without copying files")

    args = parser.parse_args()

    result, exit_code = run_packaging(
        rule_id=args.rule_id,
        model_path=args.model_path,
        property_path=args.property_path,
        rmc_output_dir=args.rmc_output_dir,
        dest_dir=args.dest_dir,
        snapshot_path=args.snapshot_path,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
