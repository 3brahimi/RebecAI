#!/usr/bin/env python3
"""Generate comprehensive per-rule report (JSON + Markdown)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from reporting_metrics import RuleReportBundle, build_rule_report_bundle
from utils import safe_path


def _bundle_to_json_payload(bundle: RuleReportBundle) -> Dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rule_id": bundle.rule_id,
        "status": bundle.status,
        "score_total": bundle.score_total,
        "score_breakdown": bundle.score_breakdown,
        "failure_reasons": bundle.failure_reasons,
        "remediation_hints": bundle.remediation_hints,
        "metrics": {
            "mutation": bundle.mutation,
            "vacuity": bundle.vacuity,
            "model_property": bundle.model_property_stats,
            "mapping_delta": bundle.mapping_delta,
        },
        "artifacts": bundle.artifacts,
    }


def _bundle_to_markdown(payload: Dict[str, Any]) -> str:
    m = payload["metrics"]
    mutation = m["mutation"]
    vacuity = m["vacuity"]
    model_stats = m["model_property"]
    mapping_delta = m["mapping_delta"]

    lines = [
        f"# Rule Report — {payload['rule_id']}",
        "",
        "## Summary",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Status | {payload['status']} |",
        f"| Score | {payload['score_total']:.2f}/100 |",
        f"| Generated at (UTC) | {payload['generated_at']} |",
        "",
        "## Score Breakdown",
        "| Component | Value |",
        "|-----------|-------|",
    ]

    for key, value in payload["score_breakdown"].items():
        lines.append(f"| {key} | {value:.2f} |")

    lines += [
        "",
        "## Mutation Testing",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Mutants generated | {mutation['mutants_generated_total']} |",
        f"| Mutants selected | {mutation['mutants_selected_total'] if mutation['mutants_selected_total'] is not None else 'N/A'} |",
        f"| Mutants executed | {mutation['mutants_executed_total']} |",
        f"| Mutants killed | {mutation['mutants_killed_total']} |",
        f"| Mutants survived | {mutation['mutants_survived_total']} |",
        f"| Mutants errors | {mutation['mutants_error_total']} |",
        f"| Mutation score | {mutation['mutation_score'] if mutation['mutation_score'] is not None else 'N/A'} |",
        "",
        "## Vacuity Diagnostics",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Checks total | {vacuity['checks_total']} |",
        f"| Checks vacuous | {vacuity['checks_vacuous']} |",
        f"| Checks non-vacuous | {vacuity['checks_non_vacuous']} |",
        f"| Checks unknown | {vacuity['checks_unknown']} |",
        f"| Overall | {vacuity['overall']} |",
        "",
    ]

    if vacuity["checks"]:
        lines += ["### Vacuity Checks"]
        for idx, check in enumerate(vacuity["checks"], 1):
            lines += [
                f"- Check {idx}",
                f"  - Assertion: {check.get('assertion_id')}",
                f"  - is_vacuous: {check.get('is_vacuous')}",
                f"  - basis: {check.get('comparison_basis')}",
                f"  - outcomes: {check.get('baseline_outcome')} -> {check.get('secondary_outcome')}",
                f"  - explanation: {check.get('explanation')}",
            ]
        lines += [""]

    lines += [
        "## Model/Property Structure Stats",
        "| Metric | Value |",
        "|--------|-------|",
        f"| State vars count | {model_stats['statevars_count']} |",
        f"| Predicates (define aliases) count | {model_stats['predicates_count']} |",
        f"| Assertions count | {model_stats['assertions_count']} |",
        "",
        "## Mapping Delta (if available)",
        "| Metric | Value |",
        "|--------|-------|",
    ]

    for key in (
        "statevars_added",
        "statevars_refined",
        "predicates_added",
        "predicates_refined",
        "assertions_added",
        "assertions_refined",
    ):
        val = mapping_delta.get(key)
        lines.append(f"| {key} | {val if val is not None else 'N/A'} |")

    if payload["failure_reasons"]:
        lines += ["", "## Failure Reasons"]
        lines.extend([f"- {x}" for x in payload["failure_reasons"]])

    if payload["remediation_hints"]:
        lines += ["", "## Remediation Hints"]
        lines.extend([f"- {x}" for x in payload["remediation_hints"]])

    lines += ["", "## Artifact Paths"]
    for k, v in payload["artifacts"].items():
        if v:
            lines.append(f"- {k}: `{v}`")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate comprehensive per-rule report")
    parser.add_argument("--rule-dir", required=True, help="Rule output directory (e.g., output/rule22)")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: same as rule-dir)")
    parser.add_argument("--json-name", default="comprehensive_report.json", help="Output JSON filename")
    parser.add_argument("--md-name", default="comprehensive_report.md", help="Output markdown filename")
    parser.add_argument("--output-json", action="store_true", help="Also print JSON to stdout")
    args = parser.parse_args()

    rule_dir = safe_path(args.rule_dir)
    if not rule_dir.exists() or not rule_dir.is_dir():
        print(f"Error: rule output directory not found: {rule_dir}", file=sys.stderr)
        sys.exit(1)

    bundle = build_rule_report_bundle(rule_dir)
    if bundle is None:
        print(
            "Error: could not build rule report; expected at least one scorecard JSON under rule dir",
            file=sys.stderr,
        )
        sys.exit(1)

    payload = _bundle_to_json_payload(bundle)
    markdown = _bundle_to_markdown(payload)

    output_dir = safe_path(args.output_dir) if args.output_dir else rule_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / args.json_name
    md_path = output_dir / args.md_name

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")

    if args.output_json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Comprehensive rule report written:\n- {json_path}\n- {md_path}")


if __name__ == "__main__":
    main()
