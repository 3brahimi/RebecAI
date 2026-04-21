#!/usr/bin/env python3
"""Gate 0 machine-check: verify all canonical step artifacts exist for a rule run.

Usage:
    python skills/rebeca_tooling/scripts/check_artifact_gaps.py --rule-id RULE_ID [--base-dir output]

Exit 0: no gaps (all required step artifacts present, schema-valid, and report files present).
Exit 1: one or more required artifacts missing or invalid.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from output_policy import report_paths
from step_schemas import validate_step_output

# (step_schema_key, filename, human description)
REQUIRED_ARTIFACTS = [
    ("step01", "step01_init.json", "Step01 init metadata"),
    ("step02", "step02_triage.json", "Step02 triage classification"),
    ("step03", "step03_abstraction.json", "Step03 abstraction contract"),
    ("step04", "step04_mapping.json", "Step04 mapping manifest"),
    ("step05", "step05_candidates.json", "Step05 candidate index"),
    ("step06", "step06_verification_gate.json", "Step06 verification gate"),
    ("step07", "step07_packaging_manifest.json", "Step07 packaging manifest"),
    ("step08", "step08_reporting.json", "Step08 reporting pointer"),
]

# Optional — only present on COLREG-fallback path; absence is not a gap
OPTIONAL_ARTIFACTS = [
    ("step02", "step02_colreg_fallback.json", "Step02 COLREG fallback artifact"),
]

# Step08 minimum completion evidence: these report files must exist on disk.
# "finish" is only unambiguous when all four are present.
STEP08_REQUIRED_REPORT_FILES = ["summary.json", "summary.md", "verification.json", "quality_gates.json"]


def _check_step08_report_files(rule_id: str, base_dir: Path) -> list[dict]:
    """Return a list of missing report-file entries (empty = all present)."""
    rp = report_paths(rule_id, base_dir)
    missing = []
    for fname in STEP08_REQUIRED_REPORT_FILES:
        fpath = rp.report_dir / fname
        if not fpath.exists():
            missing.append(
                {
                    "step": "step08",
                    "file": fname,
                    "path": str(fpath),
                    "reason": "report_file_not_found",
                }
            )
    return missing


def check_gaps(rule_id: str, base_dir: Path) -> dict:
    work_dir = base_dir / "work" / rule_id
    missing = []
    present = []
    warnings = []

    for step_key, filename, _description in REQUIRED_ARTIFACTS:
        path = work_dir / filename
        if not path.exists():
            missing.append(
                {
                    "step": step_key,
                    "file": filename,
                    "path": str(path),
                    "reason": "file_not_found",
                }
            )
            continue

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            missing.append(
                {
                    "step": step_key,
                    "file": filename,
                    "path": str(path),
                    "reason": f"json_decode_error: {exc}",
                }
            )
            continue

        violations = validate_step_output(step_key, data)
        if violations:
            missing.append(
                {
                    "step": step_key,
                    "file": filename,
                    "path": str(path),
                    "reason": "schema_invalid",
                    "violations": violations,
                }
            )
        else:
            present.append({"step": step_key, "file": filename, "path": str(path)})

    # Step08 extra check: verify the required report files exist so "finish" is unambiguous.
    # Only run this check when step08_reporting.json itself is present and valid.
    step08_artifact_ok = any(e["step"] == "step08" for e in present)
    if step08_artifact_ok:
        missing.extend(_check_step08_report_files(rule_id, base_dir))

    for step_key, filename, _description in OPTIONAL_ARTIFACTS:
        path = work_dir / filename
        if not path.exists():
            warnings.append(
                {
                    "step": step_key,
                    "file": filename,
                    "path": str(path),
                    "note": "optional artifact absent (only needed on COLREG-fallback path)",
                }
            )

    return {
        "rule_id": rule_id,
        "work_dir": str(work_dir),
        "gaps": len(missing),
        "present_count": len(present),
        "missing": missing,
        "present": present,
        "warnings": warnings,
        "gate_passed": len(missing) == 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gate 0: verify all canonical step artifacts exist and are schema-valid"
    )
    parser.add_argument("--rule-id", required=True, help="Rule identifier, e.g. COLREG-Rule22")
    parser.add_argument("--base-dir", default="output", help="Base output directory (default: output)")
    args = parser.parse_args()

    result = check_gaps(args.rule_id, Path(args.base_dir))
    print(json.dumps(result, indent=2))

    if not result["gate_passed"]:
        print(
            f"\n[GATE 0 FAILED] {result['gaps']} artifact gap(s) found for rule '{args.rule_id}'.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"\n[GATE 0 PASSED] All {result['present_count']} required artifacts present and valid"
        f" for rule '{args.rule_id}'.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
