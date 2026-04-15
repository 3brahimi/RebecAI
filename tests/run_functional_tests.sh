#!/usr/bin/env bash
set -uo pipefail

# Functional test suite — validates actual behavior, not just file presence.
# Tests: .property/.rebeca syntax via RMC (authoritative), scoring contract,
#        triage logic, fallback mapper output, and report field compliance.
#
# WHY this matters:
# - A SYNTAX ERROR in .rebeca or .property means the translation is broken
#   and RMC cannot check anything until the file parses cleanly.
# - A COUNTEREXAMPLE from RMC is NOT a syntax error — it means the actor
#   model is in an unsafe state given the property encoding. Inspect the
#   counterexample trace to determine if the model or property needs revision.
# - These tests validate the TOOLCHAIN correctness, not the safety of a model.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$PROJECT_ROOT"
SYNTAX_CHECKER="$SCRIPT_DIR/check_rebeca_syntax.py"
SCENARIOS_DIR="$REPO_ROOT/src/PromptingExperimentDoc/RebecaCodeScenarios"
RMC_JAR="${RMC_JAR:-.agents/rmc/rmc.jar}"
TOOLING_SCRIPTS="$PROJECT_ROOT/skills/rebeca_tooling/scripts"

PASSED=0
FAILED=0
ERRORS=()

pass() { echo "  PASS: $1"; ((PASSED++)); }
fail() { echo "  FAIL: $1 — $2"; ((FAILED++)); ERRORS+=("$1: $2"); }

# ─────────────────────────────────────────────────────────
# HELPER: find a rebeca scenario file for a given rule name
# ─────────────────────────────────────────────────────────
find_rebeca_for_rule() {
  local rule_name="$1"
  local scen_dir="${SCENARIOS_DIR}/${rule_name}RebecaCodeScenarios"
  if [[ -d "$scen_dir" ]]; then
    find "$scen_dir" -name "*.rebeca" | head -1
  else
    echo ""
  fi
}

# ─────────────────────────────────────────────────────────
# HELPER: extract rule name from property file path
# e.g. .../LLMLeg2Reb/V1/Rule22/prompt2.property -> Rule22
#      .../ManualTransformation.../rule22manual.property -> Rule22
# ─────────────────────────────────────────────────────────
extract_rule_name() {
  local path="$1"
  local dir
  dir=$(basename "$(dirname "$path")")
  # If it's a file like rule22manual.property, extract from filename
  local base
  base=$(basename "$path" .property)
  if [[ "$dir" == "ManualTransformation_legata_to_rebeca_properties" ]]; then
    # e.g. rule22manual -> Rule22
    echo "${base%manual}" | sed 's/^./\U&/;s/rule/Rule/;s/^r/R/'
  else
    # dir is e.g. Rule22, Rule622, Ruleb12
    echo "$dir"
  fi
}

# ─────────────────────────────────────────────────────────
# HELPER: check syntax of a (rebeca, property) pair using RMC
# Returns: "ok" | "syntax_error: <details>" | "no_rmc"
# RMC workflow: 1) RMC generates .cpp, 2) g++ compiles .cpp to executable
# ─────────────────────────────────────────────────────────
check_pair_with_rmc() {
  local model="$1"
  local prop="$2"
  local tmpout
  tmpout=$(mktemp -d /tmp/rmc_syntax_XXXX)

  if [[ ! -f "$RMC_JAR" ]]; then
    rm -rf "$tmpout"
    echo "no_rmc"
    return
  fi

  # Phase 1: RMC generates C++ from Rebeca/property
  timeout 30 java -Xmx512m -jar "$RMC_JAR" \
    -s "$model" -p "$prop" -o "$tmpout" -e TIMED_REBECA -x \
    > "$tmpout/stdout.log" 2> "$tmpout/stderr.log" || true

  # Check if .cpp files were generated (parse succeeded)
  local cpp_count
  cpp_count=$(find "$tmpout" -name "*.cpp" 2>/dev/null | wc -l | tr -d ' ')

  if [[ "$cpp_count" -eq 0 ]]; then
    # Phase 1 failed - syntax error in Rebeca/property
    local err
    err=$(grep -i "error\|syntax\|unexpected\|parse" "$tmpout/stderr.log" 2>/dev/null | head -1)
    rm -rf "$tmpout"
    echo "syntax_error: parse: ${err:-RMC produced no .cpp files}"
    return
  fi

  # Phase 2: Compile C++ with g++
  pushd "$tmpout" > /dev/null 2>&1
  if g++ ./*.cpp -w -o model.out 2> compile_stderr.log; then
    # Compilation succeeded
    popd > /dev/null 2>&1
    rm -rf "$tmpout"
    echo "ok"
    return
  else
    # Phase 2 failed - C++ compilation error
    local compile_err
    compile_err=$(head -1 compile_stderr.log 2>/dev/null)
    popd > /dev/null 2>&1
    rm -rf "$tmpout"
    echo "syntax_error: compile: ${compile_err:-g++ compilation failed}"
    return
  fi
}

echo "======================================================"
echo " FUNCTIONAL TEST SUITE"
echo "======================================================"
echo ""
echo "── SYNTAX CHECKS (via RMC when available, regex fallback) ──"

# Determine check mode
if [[ -f "$RMC_JAR" ]]; then
  echo "  [mode] RMC jar found at $RMC_JAR — using authoritative RMC syntax check"
  USE_RMC=true
else
  echo "  [mode] RMC jar not found — using regex pre-flight checker (download rmc.jar to enable full check)"
  USE_RMC=false
fi

# SYNTAX-001: Check all (rebeca, property) pairs using RMC or regex fallback
PROP_FILES=$(find "$REPO_ROOT/src/PromptingExperimentDoc" -name "*.property" 2>/dev/null | sort)
PAIR_COUNT=0
PAIR_ERRORS=0
SKIPPED=0

while IFS= read -r pf; do
  [[ -z "$pf" ]] && continue
  rule_name=$(extract_rule_name "$pf")
  rebeca_file=$(find_rebeca_for_rule "$rule_name")

  if [[ "$USE_RMC" == "true" ]] && [[ -n "$rebeca_file" ]]; then
    PAIR_COUNT=$((PAIR_COUNT + 1))
    result=$(check_pair_with_rmc "$rebeca_file" "$pf")
    if [[ "$result" == "ok" ]]; then
      : # pass silently — too many files to print each
    elif [[ "$result" == "no_rmc" ]]; then
      SKIPPED=$((SKIPPED + 1))
    else
      label="SYNTAX-RMC-$(basename "$(dirname "$pf")")-$(basename "$pf")"
      fail "$label" "$result"
      PAIR_ERRORS=$((PAIR_ERRORS + 1))
    fi
  else
    # Fallback: regex pre-flight check
    PAIR_COUNT=$((PAIR_COUNT + 1))
    if python3 "$SYNTAX_CHECKER" -- "$pf" > /dev/null 2>&1; then
      : # clean
    else
      details=$(python3 "$SYNTAX_CHECKER" -- "$pf" 2>/dev/null | grep "Line " | head -3 | tr '\n' '; ')
      fail "SYNTAX-REGEX-$(basename "$(dirname "$pf")")-$(basename "$pf")" "$details"
      PAIR_ERRORS=$((PAIR_ERRORS + 1))
    fi
  fi
done <<< "$PROP_FILES"

if [[ $PAIR_COUNT -eq 0 ]]; then
  echo "  SKIP: No .property files found"
elif [[ $PAIR_ERRORS -eq 0 ]]; then
  if [[ "$USE_RMC" == "true" ]]; then
    pass "SYNTAX-001: All $PAIR_COUNT property files pass RMC syntax check ($SKIPPED skipped — no matching rebeca)"
  else
    pass "SYNTAX-001: All $PAIR_COUNT property files pass regex pre-flight check"
  fi
fi

# SYNTAX-002: .rebeca files — property blocks must not be embedded in model file
REBECA_FILES=$(find "$REPO_ROOT/src" -name "*.rebeca" 2>/dev/null)
REBECA_COUNT=0
REBECA_ERRORS=0
while IFS= read -r rf; do
  [[ -z "$rf" ]] && continue
  REBECA_COUNT=$((REBECA_COUNT + 1))
  if grep -q "^property {" "$rf" 2>/dev/null; then
    fail "SYNTAX-REBECA-$(basename "$rf")" "property block inside .rebeca (must be in a separate .property file)"
    REBECA_ERRORS=$((REBECA_ERRORS + 1))
  fi
done <<< "$REBECA_FILES"
if [[ $REBECA_COUNT -eq 0 ]]; then
  echo "  SKIP: No .rebeca files found in src/"
elif [[ $REBECA_ERRORS -eq 0 ]]; then
  pass "SYNTAX-002: All $REBECA_COUNT .rebeca files pass structure check"
fi

# SYNTAX-003: self-test — verify regex checker catches forbidden operator
tmpfile=$(mktemp /tmp/bad_prop_XXXX.property)
echo "property { Assertion { R: condA -> condB; } }" > "$tmpfile"
if python3 "$SYNTAX_CHECKER" "$tmpfile" > /dev/null 2>&1; then
  fail "SYNTAX-003" "Regex checker FAILED to detect forbidden -> operator (false-negative risk!)"
else
  pass "SYNTAX-003: Regex checker correctly detects -> as forbidden operator"
fi
rm -f "$tmpfile"

# SYNTAX-004: self-test — verify checker passes clean property
tmpfile=$(mktemp /tmp/good_prop_XXXX.property)
printf 'property {\n  define { isLong = (s1.length > 50); }\n  Assertion { Rule: !isLong || s1.hasLight; }\n}\n' > "$tmpfile"
if python3 "$SYNTAX_CHECKER" "$tmpfile" > /dev/null 2>&1; then
  pass "SYNTAX-004: Regex checker correctly passes clean property"
else
  fail "SYNTAX-004" "Checker incorrectly flagged a valid property file"
fi
rm -f "$tmpfile"

# SYNTAX-005: Verify RMC C++ compilation works with known-good model
if [[ "$USE_RMC" == "true" ]]; then
  tmpdir=$(mktemp -d /tmp/rmc_compile_test_XXXX)

  cat > "$tmpdir/test.rebeca" << 'REBECA_EOF'
reactiveclass Ship(10) {
  statevars {
    int length;
  }
  Ship() {
    length = 50;
  }
  msgsrv tick() {
    length = length + 1;
  }
}
main {
  Ship s1():();
}
REBECA_EOF

  cat > "$tmpdir/test.property" << 'PROP_EOF'
property {
  define {
    isLong = (s1.length > 40);
  }
  Assertion {
    TestRule: isLong;
  }
}
PROP_EOF

  # Phase 1: RMC generates C++
  if timeout 30 java -Xmx512m -jar "$RMC_JAR" -s "$tmpdir/test.rebeca" -p "$tmpdir/test.property" -o "$tmpdir/out" -e TIMED_REBECA -x > /dev/null 2>&1; then
    # Check if .cpp files were generated
    if ls "$tmpdir/out/"*.cpp 1>/dev/null 2>&1; then
      # Phase 2: Compile C++ with g++
      pushd "$tmpdir/out" > /dev/null
      if g++ ./*.cpp -w -o model.out 2> compile_err.log; then
        if [[ -f model.out ]]; then
          pass "SYNTAX-005: RMC C++ compilation works (known-good model: parse + compile succeeded)"
        else
          fail "SYNTAX-005" "g++ reported success but no executable found"
        fi
      else
        fail "SYNTAX-005" "RMC generated C++ but g++ compilation failed (check g++ installation: g++ --version)"
      fi
      popd > /dev/null
    else
      fail "SYNTAX-005" "RMC succeeded but no .cpp files generated"
    fi
  else
    fail "SYNTAX-005" "RMC failed on known-good model (check RMC installation)"
  fi

  rm -rf "$tmpdir"
else
  echo "  SKIP: SYNTAX-005 (RMC not available — run download_rmc.sh to enable)"
fi

echo ""

# SCORING-001: score_total in [0, 100] for each verify status
for status in pass fail timeout blocked unknown; do
  result=$(PYTHONPATH="$TOOLING_SCRIPTS" python3 "$TOOLING_SCRIPTS/score_single_rule.py" \
    --rule-id "Test-Rule" --verify-status "$status" --output-json 2>/dev/null)
  if [[ -z "$result" ]]; then
    fail "SCORING-001-$status" "Script produced no output"
    continue
  fi
  score=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('score_total','MISSING'))" 2>/dev/null)
  if [[ "$score" == "MISSING" ]]; then
    fail "SCORING-001-$status" "Missing score_total field"
  elif python3 -c "assert 0 <= $score <= 100" 2>/dev/null; then
    pass "SCORING-001-$status: score_total=$score (in [0,100])"
  else
    fail "SCORING-001-$status" "score_total=$score is out of [0,100]"
  fi
done

# SCORING-002: score_breakdown has exactly the 4 contract-required fields
result=$(PYTHONPATH="$TOOLING_SCRIPTS" python3 "$TOOLING_SCRIPTS/score_single_rule.py" \
  --rule-id "Test-Rule" --verify-status pass --output-json 2>/dev/null)
missing_fields=""
for field in syntax semantic_alignment verification_outcome integrity; do
  if ! echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); assert '$field' in d.get('score_breakdown',{})" 2>/dev/null; then
    missing_fields="$missing_fields $field"
  fi
done
if [[ -n "$missing_fields" ]]; then
  fail "SCORING-002" "score_breakdown missing required fields:$missing_fields"
else
  pass "SCORING-002: score_breakdown has all 4 contract fields"
fi

# SCORING-002B: top-level dynamic scoring evidence fields are present
missing_meta=""
for field in mutation_score vacuity is_hallucination; do
  if ! echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); assert '$field' in d" 2>/dev/null; then
    missing_meta="$missing_meta $field"
  fi
done
if [[ -n "$missing_meta" ]]; then
  fail "SCORING-002B" "scorecard missing dynamic scoring fields:$missing_meta"
else
  pass "SCORING-002B: dynamic scoring evidence fields are present"
fi

# SCORING-003: breakdown values sum to score_total
total=$(echo "$result" | python3 -c "
import sys,json
d=json.load(sys.stdin)
bd=d.get('score_breakdown',{})
total=sum(bd.values())
score=d.get('score_total',0)
print('MATCH' if total==score else f'MISMATCH bd_sum={total} score_total={score}')
" 2>/dev/null)
if [[ "$total" == "MATCH" ]]; then
  pass "SCORING-003: score_breakdown values sum to score_total"
else
  fail "SCORING-003" "$total"
fi

# SCORING-004: confidence in [0, 1]
confidence=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('confidence','MISSING'))" 2>/dev/null)
if python3 -c "assert 0.0 <= $confidence <= 1.0" 2>/dev/null; then
  pass "SCORING-004: confidence=$confidence (in [0,1])"
else
  fail "SCORING-004" "confidence=$confidence out of [0,1]"
fi

# SCORING-005: mapping_path is one of the allowed values
mapping=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('mapping_path','MISSING'))" 2>/dev/null)
if [[ "$mapping" == "legata" || "$mapping" == "colreg-fallback" || "$mapping" == "blocked" ]]; then
  pass "SCORING-005: mapping_path='$mapping' (valid)"
else
  fail "SCORING-005" "mapping_path='$mapping' not in [legata, colreg-fallback, blocked]"
fi

# ─────────────────────────────────────────────────────────
# CATEGORY: TRIAGE — classifier logic correctness
# ─────────────────────────────────────────────────────────
echo ""
echo "── TRIAGE LOGIC CHECKS ──"

# TRIAGE-001: missing file → not-formalized
status=$(PYTHONPATH="$TOOLING_SCRIPTS" python3 "$TOOLING_SCRIPTS/classify_rule_status.py" \
  --legata-path nonexistent_file_xyz.legata --output-json 2>/dev/null | \
  python3 -c "import sys,json; print(json.load(sys.stdin).get('status','ERROR'))" 2>/dev/null)
if [[ "$status" == "not-formalized" ]]; then
  pass "TRIAGE-001: missing file → not-formalized"
else
  fail "TRIAGE-001" "Expected not-formalized, got: $status"
fi

# TRIAGE-002: TODO marker → todo-placeholder
tmpfile=$(mktemp ./test_rule_XXXX.legata)
printf "TODO: formalize this rule\n" > "$tmpfile"
status=$(PYTHONPATH="$TOOLING_SCRIPTS" python3 "$TOOLING_SCRIPTS/classify_rule_status.py" \
  --legata-path "$tmpfile" --output-json 2>/dev/null | \
  python3 -c "import sys,json; print(json.load(sys.stdin).get('status','ERROR'))" 2>/dev/null)
rm -f "$tmpfile"
if [[ "$status" == "todo-placeholder" ]]; then
  pass "TRIAGE-002: TODO content → todo-placeholder"
else
  fail "TRIAGE-002" "Expected todo-placeholder, got: $status"
fi

# TRIAGE-003: all 3 sections, substantial content → formalized
tmpfile=$(mktemp ./test_rule_XXXX.legata)
cat > "$tmpfile" << 'LEGATA'
clause Rule-Test {
  condition: OS.Length > meters(50) and OS.Type is PowerDriven
  exclude: OS.Type == Sailing or OS.Length < meters(20)
  assure: OS.MastheadLight == ON and OS.SternLight == ON
  This rule applies to all power-driven vessels longer than 50 meters navigating in any visibility condition.
}
LEGATA
status=$(PYTHONPATH="$TOOLING_SCRIPTS" python3 "$TOOLING_SCRIPTS/classify_rule_status.py" \
  --legata-path "$tmpfile" --output-json 2>/dev/null | \
  python3 -c "import sys,json; print(json.load(sys.stdin).get('status','ERROR'))" 2>/dev/null)
rm -f "$tmpfile"
if [[ "$status" == "formalized" ]]; then
  pass "TRIAGE-003: complete clause → formalized"
else
  fail "TRIAGE-003" "Expected formalized, got: $status"
fi

# TRIAGE-004: 2 sections → incomplete
tmpfile=$(mktemp ./test_rule_XXXX.legata)
printf "condition: vessel is moving\nassure: light is on\n" > "$tmpfile"
status=$(PYTHONPATH="$TOOLING_SCRIPTS" python3 "$TOOLING_SCRIPTS/classify_rule_status.py" \
  --legata-path "$tmpfile" --output-json 2>/dev/null | \
  python3 -c "import sys,json; print(json.load(sys.stdin).get('status','ERROR'))" 2>/dev/null)
rm -f "$tmpfile"
if [[ "$status" == "incomplete" ]]; then
  pass "TRIAGE-004: 2-section clause → incomplete"
else
  fail "TRIAGE-004" "Expected incomplete, got: $status"
fi

# TRIAGE-005: 1 section → incorrect
tmpfile=$(mktemp ./test_rule_XXXX.legata)
printf "condition: vessel is large\n" > "$tmpfile"
status=$(PYTHONPATH="$TOOLING_SCRIPTS" python3 "$TOOLING_SCRIPTS/classify_rule_status.py" \
  --legata-path "$tmpfile" --output-json 2>/dev/null | \
  python3 -c "import sys,json; print(json.load(sys.stdin).get('status','ERROR'))" 2>/dev/null)
rm -f "$tmpfile"
if [[ "$status" == "incorrect" ]]; then
  pass "TRIAGE-005: 1-section clause → incorrect"
else
  fail "TRIAGE-005" "Expected incorrect, got: $status"
fi

# ─────────────────────────────────────────────────────────
# CATEGORY: FALLBACK — mapper output correctness
# ─────────────────────────────────────────────────────────
echo ""
echo "── FALLBACK MAPPER CHECKS ──"

result=$(PYTHONPATH="$TOOLING_SCRIPTS" python3 "$TOOLING_SCRIPTS/colreg_fallback_mapper.py" \
  --rule-id "Test-99" \
  --colreg-text "Every vessel shall maintain a proper lookout and shall not impede safe passage of another vessel" \
  --output-json 2>/dev/null)

# FALLBACK-001: required fields present
for field in rule_id provisional_property confidence assumptions requires_manual_review mapping_path; do
  if echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); assert '$field' in d" 2>/dev/null; then
    pass "FALLBACK-001-$field: present"
  else
    fail "FALLBACK-001-$field" "Missing field in fallback output"
  fi
done

# FALLBACK-002: provisional_property has no forbidden operators (uses Python checker)
prop=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('provisional_property',''))" 2>/dev/null)
tmpfile=$(mktemp /tmp/test_prop_XXXX.property)
printf '%s\n' "$prop" > "$tmpfile"
violations=$(python3 "$SYNTAX_CHECKER" "$tmpfile" 2>/dev/null | grep "VIOLATIONS" | wc -l | tr -d ' ')
rm -f "$tmpfile"
if [[ "$violations" -gt 0 ]]; then
  fail "FALLBACK-002" "Provisional property contains forbidden operators"
else
  pass "FALLBACK-002: Provisional property has no forbidden operators"
fi

# FALLBACK-003: confidence is valid
confidence=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('confidence','ERROR'))" 2>/dev/null)
if [[ "$confidence" == "high" || "$confidence" == "medium" || "$confidence" == "low" ]]; then
  pass "FALLBACK-003: confidence='$confidence' (valid)"
else
  fail "FALLBACK-003" "confidence='$confidence' not in [high,medium,low]"
fi

# FALLBACK-004: mapping_path is colreg-fallback
mp=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('mapping_path','ERROR'))" 2>/dev/null)
if [[ "$mp" == "colreg-fallback" ]]; then
  pass "FALLBACK-004: mapping_path=colreg-fallback"
else
  fail "FALLBACK-004" "mapping_path='$mp' should be colreg-fallback"
fi

# FALLBACK-005: requires_manual_review is true for non-trivial text
needs_review=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('requires_manual_review','ERROR'))" 2>/dev/null)
if [[ "$needs_review" == "True" || "$needs_review" == "true" ]]; then
  pass "FALLBACK-005: requires_manual_review=true (non-trivial text)"
else
  fail "FALLBACK-005" "requires_manual_review='$needs_review' should be true"
fi

# ─────────────────────────────────────────────────────────
# CATEGORY: REPORT — aggregate contract fields
# ─────────────────────────────────────────────────────────
echo ""
echo "── REPORT CONTRACT CHECKS ──"

report=$(PYTHONPATH="$TOOLING_SCRIPTS" python3 - << 'PYEOF'
import sys
import os
from pathlib import Path

# Add tooling scripts to path
scripts_path = os.environ.get('PYTHONPATH')
if scripts_path:
    sys.path.insert(0, scripts_path)

from generate_report import ReportGenerator
from score_single_rule import RubricScorer
r = ReportGenerator()
s = RubricScorer()
r.add_scorecard(s.score_rule('Rule-A', verify_status='pass'))
r.add_scorecard(s.score_rule('Rule-B', verify_status='fail'))
r.finalize()
print(r.to_json())
PYEOF
)

# REPORT-001: all contract-required aggregate fields present
for field in total_rules rules_passed rules_failed score_mean score_min score_max success_rate status_counts fallback_usage_count top_failure_reasons; do
  if echo "$report" | python3 -c "import sys,json; d=json.load(sys.stdin); assert '$field' in d" 2>/dev/null; then
    pass "REPORT-001-$field: present"
  else
    fail "REPORT-001-$field" "Missing contract field"
  fi
done

# REPORT-002: success_rate in [0, 100]
rate=$(echo "$report" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success_rate',-1))" 2>/dev/null)
if python3 -c "assert 0 <= $rate <= 100" 2>/dev/null; then
  pass "REPORT-002: success_rate=$rate (in [0,100])"
else
  fail "REPORT-002" "success_rate=$rate out of [0,100]"
fi

# REPORT-003: status_counts has all 5 Legata statuses as keys
for key in formalized incomplete incorrect not-formalized todo-placeholder; do
  if echo "$report" | python3 -c "import sys,json; d=json.load(sys.stdin); assert '$key' in d.get('status_counts',{})" 2>/dev/null; then
    pass "REPORT-003-$key: status_counts key present"
  else
    fail "REPORT-003-$key" "status_counts missing key '$key'"
  fi
done

# ─────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────
echo ""
echo "======================================================"
echo " FUNCTIONAL TEST RESULTS: $PASSED passed, $FAILED failed"
echo "======================================================"

if [[ $FAILED -gt 0 ]]; then
  echo ""
  echo "Failures:"
  for err in "${ERRORS[@]}"; do
    echo "  ✗ $err"
  done
  exit 1
fi
