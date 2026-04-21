#!/usr/bin/env python3
"""shadow_compare.py — Parity comparison tool for FSM rollout validation.

Compares two completed pipeline runs (baseline vs FSM-driven) for the same
rule and reports any divergences in artifact presence or schema validity.
The parity gate passes only when both runs have identical artifact coverage
and all artifacts pass schema validation.

Usage:
    python shadow_compare.py \\
        --rule-id RULE_ID \\
        --baseline-dir output_legacy \\
        --fsm-dir output_fsm \\
        [--json-output results/parity_RULE_ID.json]

Exit codes:
    0  Parity gate passed — no divergences
    1  Parity gate failed — divergences detected
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from output_policy import report_paths, step_artifact_path  # noqa: E402
from step_schemas import validate_step_output  # noqa: E402

_REQUIRED_STEPS: list[tuple[str, str]] = [
    ("step01", "step01_init"),
    ("step02", "step02_triage"),
    ("step03", "step03_abstraction"),
    ("step04", "step04_mapping"),
    ("step05", "step05_candidates"),
    ("step06", "step06_verification_gate"),
    ("step07", "step07_packaging_manifest"),
    ("step08", "step08_reporting"),
]

_REQUIRED_REPORT_FILES = ("summary.json", "summary.md", "verification.json", "quality_gates.json")


def _check_run(rule_id: str, base_dir: Path) -> dict:
    """Return artifact status for one completed run."""
    artifacts: dict[str, dict] = {}
    for schema_key, artifact_step in _REQUIRED_STEPS:
        path = step_artifact_path(rule_id, artifact_step, base_dir)
        if not path.exists():
            artifacts[artifact_step] = {"present": False, "schema_valid": False, "violations": []}
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            artifacts[artifact_step] = {
                "present": True, "schema_valid": False, "violations": [f"json_decode_error: {exc}"],
            }
            continue
        violations = validate_step_output(schema_key, data)
        artifacts[artifact_step] = {
            "present": True,
            "schema_valid": len(violations) == 0,
            "violations": violations,
        }

    rp = report_paths(rule_id, base_dir)
    report_files = {
        fname: (rp.report_dir / fname).exists()
        for fname in _REQUIRED_REPORT_FILES
    }

    return {"artifacts": artifacts, "report_files": report_files}


def compare(rule_id: str, baseline_dir: Path, fsm_dir: Path) -> dict:
    baseline = _check_run(rule_id, baseline_dir)
    fsm = _check_run(rule_id, fsm_dir)

    divergences: list[dict] = []

    for artifact_step in (s for _, s in _REQUIRED_STEPS):
        b = baseline["artifacts"][artifact_step]
        f = fsm["artifacts"][artifact_step]
        if b["present"] != f["present"]:
            divergences.append({
                "type": "presence_mismatch",
                "artifact": artifact_step,
                "baseline_present": b["present"],
                "fsm_present": f["present"],
            })
        elif b["present"] and b["schema_valid"] != f["schema_valid"]:
            divergences.append({
                "type": "validity_mismatch",
                "artifact": artifact_step,
                "baseline_valid": b["schema_valid"],
                "fsm_valid": f["schema_valid"],
                "baseline_violations": b["violations"],
                "fsm_violations": f["violations"],
            })

    for fname in _REQUIRED_REPORT_FILES:
        b_has = baseline["report_files"][fname]
        f_has = fsm["report_files"][fname]
        if b_has != f_has:
            divergences.append({
                "type": "report_file_mismatch",
                "file": fname,
                "baseline_present": b_has,
                "fsm_present": f_has,
            })

    baseline_invalid = [
        s for s, d in baseline["artifacts"].items() if not d["schema_valid"]
    ]
    fsm_invalid = [
        s for s, d in fsm["artifacts"].items() if not d["schema_valid"]
    ]

    return {
        "rule_id": rule_id,
        "baseline_dir": str(baseline_dir),
        "fsm_dir": str(fsm_dir),
        "divergences": divergences,
        "baseline_invalid_artifacts": baseline_invalid,
        "fsm_invalid_artifacts": fsm_invalid,
        "parity_gate_passed": len(divergences) == 0 and not baseline_invalid and not fsm_invalid,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parity comparison for FSM rollout shadow runs"
    )
    parser.add_argument("--rule-id", required=True)
    parser.add_argument("--baseline-dir", required=True, help="Directory of baseline (legacy) run")
    parser.add_argument("--fsm-dir", required=True, help="Directory of FSM-driven run")
    parser.add_argument("--json-output", help="Write JSON report to this path")
    args = parser.parse_args()

    result = compare(
        rule_id=args.rule_id,
        baseline_dir=Path(args.baseline_dir),
        fsm_dir=Path(args.fsm_dir),
    )

    output = json.dumps(result, indent=2)
    print(output)

    if args.json_output:
        Path(args.json_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_output).write_text(output, encoding="utf-8")

    if result["parity_gate_passed"]:
        print("\n[PARITY GATE PASSED]", file=sys.stderr)
        sys.exit(0)
    else:
        print(
            f"\n[PARITY GATE FAILED] {len(result['divergences'])} divergence(s) detected.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
