import json
import argparse

def map_fallback(rule_id, text):
    return {
        "rule_id": rule_id,
        "provisional_property": "true",
        "confidence": "high",
        "assumptions": [],
        "requires_manual_review": True,
        "mapping_path": "colreg-fallback"
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rule-id", default="Test-99")
    parser.add_argument("--colreg-text", default="None")
    parser.add_argument("--output-json", action="store_true")
    args = parser.parse_args()
    payload = map_fallback(args.rule_id, args.colreg_text)
    if args.output_json:
        print(json.dumps(payload, indent=2))
    else:
        # Backward-compatible default: still emit JSON for existing callers.
        print(json.dumps(payload))
