#!/usr/bin/env python3
"""
Classify rule formalization status based on Legata input.
Returns: formalized | incomplete | incorrect | not-formalized | todo-placeholder
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any

from utils import safe_path, safe_open

class RuleStatusClassifier:
    """Classifies Legata rule formalization status."""
    
    def classify(self, legata_path: str) -> Dict[str, Any]:
        """
        Classify a Legata rule's formalization status.
        
        Returns dict with:
            - status: one of [formalized, incomplete, incorrect, not-formalized, todo-placeholder]
            - clause_count: number of clauses in rule
            - evidence: list of findings
            - defects: list of identified defects
            - next_action: recommended next action
        """
        
        result = {
            "rule_id": safe_path(legata_path).stem,
            "status": "unknown",
            "clause_count": 0,
            "evidence": [],
            "defects": [],
            "next_action": "Manual review required"
        }
        
        try:
            with safe_open(legata_path, 'r') as f:
                content = f.read()
                result["clause_count"] = content.count("clause")
        except FileNotFoundError:
            result["status"] = "not-formalized"
            result["evidence"].append("Legata file not found")
            result["next_action"] = "Create Legata formalization from COLREG text"
            return result
        
        # Check for TODO markers
        if "TODO" in content or "todo" in content or "FIXME" in content:
            result["status"] = "todo-placeholder"
            result["evidence"].append("TODO/FIXME marker found in Legata")
            result["defects"].append("Incomplete formalization (marked as TODO)")
            result["next_action"] = "Complete Legata formalization"
            return result
        
        # Check for required sections (condition, exclude, assure)
        has_condition = "condition" in content
        has_exclude = "exclude" in content or "exclusion" in content
        has_assure = "assure" in content or "assurance" in content
        
        evidence_count = sum([has_condition, has_exclude, has_assure])
        
        if evidence_count == 0:
            result["status"] = "not-formalized"
            result["evidence"].append("No condition/exclude/assure sections found")
            result["next_action"] = "Formalize rule with COLREG guidance"
            return result
        
        if evidence_count == 3:
            # All sections present - check for common issues
            if len(content.strip()) < 100:
                result["status"] = "incomplete"
                result["evidence"].append("All sections present but sparse content")
                result["defects"].append("Insufficient detail in rule specification")
                result["next_action"] = "Expand with explicit actor conditions"
            else:
                result["status"] = "formalized"
                result["evidence"].append("Condition section: Present")
                result["evidence"].append("Exclude section: Present")
                result["evidence"].append("Assure section: Present")
                result["next_action"] = "Proceed to Rebeca model generation"
            return result
        
        if evidence_count == 2:
            result["status"] = "incomplete"
            result["evidence"].append("Some sections missing")
            if not has_condition:
                result["defects"].append("Missing condition section")
            if not has_exclude:
                result["defects"].append("Missing exclude section")
            if not has_assure:
                result["defects"].append("Missing assure section")
            result["next_action"] = "Add missing sections"
            return result
        
        # 1 section present
        result["status"] = "incorrect"
        result["evidence"].append("Only 1 of 3 required sections present")
        result["defects"].append("Malformed Legata structure")
        result["next_action"] = "Rewrite rule with proper condition/exclude/assure structure"
        return result


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Classify rule formalization status")
    parser.add_argument("--legata-path", required=True, help="Path to Legata file")
    parser.add_argument("--output-json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    classifier = RuleStatusClassifier()
    result = classifier.classify(args.legata_path)
    
    if args.output_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Rule: {result['rule_id']}")
        print(f"Status: {result['status']}")
        print(f"Clauses: {result['clause_count']}")
        print(f"\nEvidence:")
        for ev in result['evidence']:
            print(f"  - {ev}")
        if result['defects']:
            print(f"\nDefects:")
            for defect in result['defects']:
                print(f"  - {defect}")
        print(f"\nNext Action: {result['next_action']}")


if __name__ == "__main__":
    main()
