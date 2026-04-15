#!/usr/bin/env python3
"""
Generate aggregate scoring report with JSON and Markdown output.
Supports both single-rule and multi-rule reporting with remediation guidance.
"""

import json
import sys
from typing import Dict, List, Any, Optional
from pathlib import Path

from utils import safe_path

class ReportGenerator:
    """Generates compact and detailed scoring reports."""
    
    def __init__(self):
        self.report_data = {
            "execution_timestamp": None,
            "total_rules": 0,
            "rules_passed": 0,
            "rules_failed": 0,
            "score_mean": 0.0,
            "score_min": 0,
            "score_max": 0,
            "success_rate": 0.0,
            "status_counts": {
                "formalized": 0,
                "incomplete": 0,
                "incorrect": 0,
                "not-formalized": 0,
                "todo-placeholder": 0
            },
            "fallback_usage_count": 0,
            "blocked_rules_count": 0,
            "per_rule_scorecards": [],
            "top_failure_reasons": [],
            "aggregate_remediation_hints": []
        }
    
    def add_scorecard(self, scorecard: Dict[str, Any]) -> None:
        """Add a rule scorecard to the report."""
        self.report_data["per_rule_scorecards"].append(scorecard)
        self.report_data["total_rules"] += 1
        
        score = scorecard.get("score_total", 0)
        status = scorecard.get("status", "Unknown")

        # Aggregate pass/fail (contract fields: rules_passed, rules_failed)
        if status == "Pass":
            self.report_data["rules_passed"] += 1
        elif status in ("Fail", "Blocked", "Conditional"):
            self.report_data["rules_failed"] += 1

        # Aggregate by input_status for status_counts
        input_status = scorecard.get("input_status", "not-formalized")
        if input_status in self.report_data["status_counts"]:
            self.report_data["status_counts"][input_status] += 1

        # Track fallback usage
        if scorecard.get("mapping_path") == "colreg-fallback":
            self.report_data["fallback_usage_count"] += 1
        
        # Track blocked rules
        if status == "Blocked":
            self.report_data["blocked_rules_count"] += 1
        
        # Collect failure reasons
        for reason in scorecard.get("failure_reasons", []):
            if reason not in self.report_data["top_failure_reasons"]:
                self.report_data["top_failure_reasons"].append(reason)
        
        # Collect remediation hints
        for hint in scorecard.get("remediation_hints", []):
            if hint not in self.report_data["aggregate_remediation_hints"]:
                self.report_data["aggregate_remediation_hints"].append(hint)
    
    def finalize(self) -> None:
        """Finalize aggregate metrics."""
        from datetime import datetime
        
        self.report_data["execution_timestamp"] = datetime.now().isoformat()
        
        if self.report_data["total_rules"] == 0:
            return
        
        # Calculate statistics
        scores = [sc.get("score_total", 0) for sc in self.report_data["per_rule_scorecards"]]
        self.report_data["score_min"] = min(scores) if scores else 0
        self.report_data["score_max"] = max(scores) if scores else 0
        self.report_data["score_mean"] = sum(scores) / len(scores) if scores else 0.0
        
        # Success rate: rules_passed / total_rules
        self.report_data["success_rate"] = (
            self.report_data["rules_passed"] / self.report_data["total_rules"]
        ) * 100.0
    
    def to_json(self) -> str:
        """Export report as JSON."""
        return json.dumps(self.report_data, indent=2)
    
    def to_markdown(self) -> str:
        """Export report as Markdown."""
        md = []
        md.append("# Legata→Rebeca Scoring Report\n")
        
        md.append(f"**Execution Time**: {self.report_data['execution_timestamp']}\n")
        md.append(f"**Total Rules Processed**: {self.report_data['total_rules']}\n")
        
        # Summary metrics table
        md.append("\n## Results\n")
        md.append("| Outcome | Count |")
        md.append("|---------|-------|")
        md.append(f"| Passed | {self.report_data['rules_passed']} |")
        md.append(f"| Failed | {self.report_data['rules_failed']} |")

        md.append("\n## Status Counts\n")
        md.append("| Input Status | Count |")
        md.append("|-------------|-------|")
        for status_key, count in self.report_data["status_counts"].items():
            md.append(f"| {status_key} | {count} |")
        
        md.append("\n## Aggregate Metrics\n")
        md.append(f"- **Success Rate**: {self.report_data['success_rate']:.1f}%")
        md.append(f"- **Average Score**: {self.report_data['score_mean']:.2f}/100")
        md.append(f"- **Score Range**: {self.report_data['score_min']}-{self.report_data['score_max']}")
        md.append(f"- **COLREG Fallback Usage**: {self.report_data['fallback_usage_count']} rules")
        md.append(f"- **Blocked Rules**: {self.report_data['blocked_rules_count']} rules")
        
        # Per-rule scorecards
        md.append("\n## Per-Rule Scorecards\n")
        md.append("| Rule ID | Score | Status | Input | Mapping |")
        md.append("|---------|-------|--------|-------|---------|")
        for sc in self.report_data["per_rule_scorecards"]:
            rule_id = sc.get("rule_id", "-")
            score = sc.get("score_total", 0)
            status = sc.get("status", "Unknown")
            input_status = sc.get("input_status", "unknown")
            mapping = sc.get("mapping_path", "legata")
            md.append(f"| {rule_id} | {score}/100 | {status} | {input_status} | {mapping} |")
        
        # Top failure reasons
        if self.report_data["top_failure_reasons"]:
            md.append("\n## Top Failure Reasons\n")
            for i, reason in enumerate(self.report_data["top_failure_reasons"][:5], 1):
                md.append(f"{i}. {reason}")
        
        # Remediation guidance
        if self.report_data["aggregate_remediation_hints"]:
            md.append("\n## Remediation Guidance\n")
            for hint in self.report_data["aggregate_remediation_hints"][:10]:
                md.append(f"- {hint}")
        
        return "\n".join(md)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate scoring report")
    parser.add_argument("--input-scores", help="JSON file with scored rules")
    parser.add_argument("--output-dir", default="reports/", help="Output directory")
    parser.add_argument("--format", choices=["json", "markdown", "both"], default="both")
    
    args = parser.parse_args()
    
    generator = ReportGenerator()
    
    # Load input scores if provided
    if args.input_scores:
        with open(args.input_scores) as f:
            scores = json.load(f)
            if isinstance(scores, list):
                for scorecard in scores:
                    generator.add_scorecard(scorecard)
            else:
                generator.add_scorecard(scores)
    
    generator.finalize()
    
    # Create output directory
    safe_path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    # Write outputs
    if args.format in ["json", "both"]:
        with open(f"{args.output_dir}/report.json", "w") as f:
            f.write(generator.to_json())
        print(f"✓ Written {args.output_dir}/report.json")
    
    if args.format in ["markdown", "both"]:
        with open(f"{args.output_dir}/report.md", "w") as f:
            f.write(generator.to_markdown())
        print(f"✓ Written {args.output_dir}/report.md")


if __name__ == "__main__":
    main()
