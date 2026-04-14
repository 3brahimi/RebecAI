#!/usr/bin/env bash
set -euo pipefail

# Run acceptance tests AT-001 through AT-022

echo "Running Acceptance Tests..."
echo ""

PASSED=0
FAILED=0

# AT-001: Prescribed Workflow
echo -n "AT-001 (Prescribed Workflow): "
if [[ -f ".agents/agents/legata-formalization.agent.md" ]]; then
  if grep -q "WF-01" ".agents/agents/legata-formalization.agent.md"; then
    echo "PASS"
    ((PASSED++))
  else
    echo "FAIL"
    ((FAILED++))
  fi
else
  echo "FAIL"
  ((FAILED++))
fi

# AT-002: Agent Structure
echo -n "AT-002 (Agent Structure): "
if grep -q "Rebeca" ".agents/agents/legata-formalization.agent.md"; then
  echo "PASS"
  ((PASSED++))
else
  echo "FAIL"
  ((FAILED++))
fi

# AT-021: No Requirements Leakage
echo -n "AT-021 (No Leakage): "
if ! grep -q "FR-" ".agents/agents/legata-formalization.agent.md" 2>/dev/null; then
  echo "PASS"
  ((PASSED++))
else
  echo "FAIL"
  ((FAILED++))
fi

# AT-022: Rebeca Guidance Skill
echo -n "AT-022 (Rebeca Skill): "
if [[ -f ".agents/skills/rebeca-modeling-guidelines/SKILL.md" ]]; then
  echo "PASS"
  ((PASSED++))
else
  echo "FAIL"
  ((FAILED++))
fi

echo ""
echo "Results: $PASSED passed, $FAILED failed"
