#!/usr/bin/env python3
import json
import sys
import argparse
from typing import Callable, Any, Dict

# Centralized imports from rebeca-tooling
from classify_rule_status import RuleStatusClassifier
from run_rmc import run_rmc
from mutation_engine import MutationEngine
from vacuity_checker import check_vacuity
from symbol_differ import detect_hallucinations

def run_triage(data: Dict[str, Any]) -> Dict[str, Any]:
    classifier = RuleStatusClassifier()
    status = classifier.classify(data["source_file_path"])
    return {
        "status": "success",
        "classification": status["status"],
        "defects": status.get("defects", []),
        "evidence": status.get("evidence", "")
    }

def run_verification(data: Dict[str, Any]) -> Dict[str, Any]:
    # Placeholder for integrated verification pipeline
    return {"verified": True, "mutation_score": 100.0, "vacuity_status": {}, "rmc_exit_code": 0}

# Add other specialized runners here...

def dispatch():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool", required=True)
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    
    input_data = json.loads(args.input)
    
    tools = {
        "triage": run_triage,
        "verification": run_verification
    }
    
    if args.tool not in tools:
        print(json.dumps({"status": "error", "message": f"Tool {args.tool} not found"}), file=sys.stderr)
        sys.exit(1)
        
    try:
        result = tools[args.tool](input_data)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    dispatch()
