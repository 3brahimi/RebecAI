#!/usr/bin/env bash
set -uo pipefail

# This script was updated to match the new multi-agent JSON contract.
# It now parses JSON fields explicitly to ensure compliance.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLING_SCRIPTS="$SCRIPT_DIR/../skills/rebeca_tooling/scripts"

# Helper for JSON field extraction
check_json_field() {
  local json="$1"
  local field="$2"
  echo "$json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$field', 'MISSING'))"
}

echo "Running functional tests..."

# 1. Test Fallback Mapper
result=$(PYTHONPATH="$TOOLING_SCRIPTS" python3 "$TOOLING_SCRIPTS/colreg_fallback_mapper.py" --rule-id "Test-99" --colreg-text "Lookout" 2>/dev/null)
# Expecting: {"rule_id": "Test-99", "provisional_property": "true", "confidence": "high", "assumptions": [], "requires_manual_review": true, "mapping_path": "colreg-fallback"}

for field in rule_id provisional_property confidence assumptions requires_manual_review mapping_path; do
  val=$(check_json_field "$result" "$field")
  if [[ "$val" == "MISSING" ]]; then
    echo "FAIL: FALLBACK-001-$field — Missing field"
    exit 1
  fi
done
# Check specific enum
conf=$(check_json_field "$result" "confidence")
if [[ "$conf" != "high" && "$conf" != "medium" && "$conf" != "low" ]]; then
  echo "FAIL: FALLBACK-003 — invalid confidence"
  exit 1
fi
echo "PASS: All fallback tests passed."

# 2. Test Scoring (SCORING-002)
report=$(PYTHONPATH="$TOOLING_SCRIPTS" python3 - << 'PYEOF'
import sys
from skills.rebeca_tooling.scripts.generate_report import ReportGenerator
r = ReportGenerator()
# Simulate a passing scorecard with the NEW required fields
r.add_scorecard({
    "rule_id": "Rule-A", "status": "Pass", "score_total": 100,
    "score_breakdown": {"integrity": 25, "syntax": 25, "semantic_alignment": 25, "verification_outcome": 25},
    "mutation_score": 1.0, "vacuity": {"is_vacuous": False}, "is_hallucination": False
})
r.finalize()
print(r.to_json())
PYEOF
)

# Check integrity field in breakdown
val=$(echo "$report" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['per_rule_scorecards'][0]['score_breakdown'].get('integrity', 'MISSING'))")
if [[ "$val" == "MISSING" ]]; then
    echo "FAIL: SCORING-002 — missing integrity"
    exit 1
fi
echo "PASS: All scoring tests passed."

echo "All tests passed successfully."
