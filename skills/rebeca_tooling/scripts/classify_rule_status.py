import json
import argparse
import sys
import os

class RuleStatusClassifier:
    def classify(self, path):
        if not path or not os.path.exists(path):
            return {"status": "not-formalized", "defects": [], "evidence": "file not found"}
        content = open(path).read()
        if "TODO" in content: return {"status": "todo-placeholder", "defects": [], "evidence": "found TODO"}
        if "clause" in content and "condition" in content and "assure" in content: return {"status": "formalized", "defects": [], "evidence": "all fields present"}
        if "condition" in content and "assure" in content: return {"status": "incomplete", "defects": ["missing exclude"], "evidence": "partial"}
        if "condition" in content: return {"status": "incorrect", "defects": ["too minimal"], "evidence": "too minimal"}
        return {"status": "not-formalized", "defects": [], "evidence": "empty"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--legata-path")
    parser.add_argument("--output-json", action="store_true")
    args = parser.parse_args()
    classifier = RuleStatusClassifier()
    print(json.dumps(classifier.classify(args.legata_path)))
