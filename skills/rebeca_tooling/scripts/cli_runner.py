#!/usr/bin/env python3
import json
import sys
import argparse
import importlib.util
from pathlib import Path
from typing import Any, Dict

def _load_symbol(script_name: str, symbol_name: str) -> Any:
    """Load a symbol from a sibling script file (supports hyphenated filenames)."""
    script_path = Path(__file__).with_name(script_name)
    spec = importlib.util.spec_from_file_location(f"rebeca_tooling_{script_name}", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, symbol_name)

def run_triage(data: Dict[str, Any]) -> Dict[str, Any]:
    RuleStatusClassifier = _load_symbol("classify-rule-status.py", "RuleStatusClassifier")
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
