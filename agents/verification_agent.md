---
name: verification_agent
description: |
  Step06 specialist for RMC verification, vacuity checking, and mutation scoring.
  Runs three sequential phases: Phase0 (syntax via RMC), Phase1 (semantics via
  mutation→RMC), Phase2 (vacuity via RMC). Scoring is only valid after all phases complete.
schema: skills/rebeca_tooling/schemas/verification-agent.schema.json
skills:
  - rebeca_tooling
  - rebeca_mutation
  - rebeca_hallucination
  - rebeca_handbook
---

# Step06 Subagent: Verification and Mutation Scoring

## Goal

Validate generated artifacts through three sequential verification phases.
All three phases must complete before a score can be computed.
Return a fully machine-actionable outcome with per-phase results.

## Input Schema

| Field              | Type    | Required | Description                                         |
|--------------------|---------|----------|-----------------------------------------------------|
| `source_file_path` | string  | yes      | Rule identifier (e.g. `Rule-22`)                    |
| `model_path`       | string  | yes      | Path to `.rebeca` model file                        |
| `property_path`    | string  | yes      | Path to `.property` file                            |
| `jar_path`         | string  | yes      | Path to `rmc.jar`                                   |
| `output_dir`       | string  | yes      | `output/verification/<rule_id>/<run_id>/` — obtained via `output_policy.verification_paths(rule_id, run_id).run_dir` |
| `timeout`          | integer | no       | Per-invocation timeout in seconds (≥1, default 120) |

## Verification Pipeline (three sequential phases)

```
Phase0 — Syntax
  run_rmc(model, property, jar, output_dir, timeout)
      │
      ├─ exit_code != 0 ──► STOP: emit contract with verified=false
      │                            phase0_passed=false; skip Phase1 + Phase2
      │
      └─ exit_code == 0 ──► phase0_passed=true; proceed to Phase1

Phase1 — Semantics (mutation testing)
  MutationEngine.generate_all()  [8 strategies]
      │   For each mutant:
      │     run_rmc_detailed(mutant_model_or_property, jar, output_dir_mut, timeout,
      │                      run_model_outcome=true)
      │       killed  if semantic outcome flips vs baseline (satisfied ↔ cex)
      │       survived if semantic outcome unchanged
      │       error   if baseline/mutant outcome is non-comparable
      └─► mutation_score = killed / total × 100.0
          phase1_passed = mutation_score >= 80.0

Phase2 — Vacuity
  vacuity_checker(jar, model, property, output_dir, timeout)
      └─► vacuity_status { is_vacuous, precondition_used, explanation }
          phase2_passed = is_vacuous == false

Phase3 — Integrity (hallucination audit)   ← always runs, independent of Phase0 outcome
  symbol_differ(snapshot, current_model, current_property, rmc_exit_code, rmc_stderr)
      └─► { is_hallucination, hallucination_type, offending_symbols }
          phase3_passed = is_hallucination == false
          hallucination_type ∈ { "dead_code", "reference", null }

─────────────────────────────────────────────────────────────
Scoring gate: ALL four phases must complete before the
coordinator can compute a score:
  phase0_passed=true  (syntax)
  phase1_passed=true  (mutation_score >= 80.0)
  phase2_passed=true  (is_vacuous == false)
  phase3_passed=true  (is_hallucination == false)

phase3 is the ONLY phase that always runs regardless of phase0.
phase1 and phase2 only run when phase0 exit_code == 0.
─────────────────────────────────────────────────────────────
```

## Phase0 — RMC Syntax/Compilation Check

```bash
python3 <scripts>/run_rmc.py \
  --jar <jar> \
  --model $MODEL \
  --property $PROPERTY \
  --output-dir $OUTPUT_DIR/rmc \
  --timeout-seconds 120 \
  --run-model-outcome \
  --output-file $OUTPUT_DIR/rmc_details.json
```

### Exit Code Classification

| Exit Code | `rmc_outcome`        | `phase0_passed` |
|-----------|----------------------|-----------------|
| 0         | `verified`           | `true`          |
| 1         | `invalid_inputs`     | `false`         |
| 3         | `timeout`            | `false`         |
| 4         | `cpp_compile_failed` | `false`         |
| 5         | `parse_failed`       | `false`         |
| other     | `unknown`            | `false`         |

**Do not proceed to Phase1 or Phase2 if Phase0 exit code != 0.**

## Phase1 — Semantic Strength (mutation testing)

Only run if Phase0 passed (`rmc_exit_code == 0`).

```bash
python3 <scripts>/mutation_engine.py \
  --rule-id $RULE_ID \
  --model $MODEL \
  --property $PROPERTY \
  --strategy all \
  --output-file $OUTPUT_DIR/mutation_candidates.json
```

Then execute a bounded kill-run to compute a mutation score:

```bash
python3 <scripts>/mutation_engine.py \
  --rule-id $RULE_ID \
  --model $MODEL \
  --property $PROPERTY \
  --strategy all \
  --run-with-jar <jar> \
  --run-with-model $MODEL \
  --run-with-property $PROPERTY \
  --run-timeout 60 \
  --max-mutants 50 \
  --total-timeout 600 \
  --seed 42 \
  --output-file $OUTPUT_DIR/mutation_killrun.json
```

For each generated mutant, run RMC:
- **Killed**: mutant semantic outcome flips relative to baseline (`satisfied` ↔ `cex`)
- **Survived**: mutant semantic outcome matches baseline
- **Error**: semantic outcome unavailable (`unknown`/timeout/non-comparable)

```
mutation_score = killed / total × 100.0
phase1_passed  = mutation_score >= 80.0
```

### Mutation Strategies (8 total)

**Model-side** (`.rebeca`): `transition_bypass` · `predicate_flip` · `assignment_mutation`

**Property-side** (`.property`): `comparison_value_mutation` · `boolean_predicate_negation` · `assertion_negation` · `assertion_predicate_inversion` · `logical_swap` · `variable_swap`

See `rebeca_mutation` skill for strategy details and Python workflow.

## Phase2 — Vacuity Check

Only run if Phase0 passed. Run in parallel with Phase1 (both require Phase0).

```bash
python3 <scripts>/vacuity_checker.py \
  --jar <jar> \
  --model $MODEL \
  --property $PROPERTY \
  --output-dir $OUTPUT_DIR \
  --timeout-seconds 60 \
  --output-file $OUTPUT_DIR/vacuity_check.json \
  --output-json
```

```
phase2_passed = vacuity_status.is_vacuous == false
```

A vacuous property passes RMC trivially because its precondition is never reachable. If `is_vacuous == true`, the property needs a stronger precondition — route back to Step05.

## Phase3 — Integrity / Hallucination Audit

**Always runs** — independent of Phase0 outcome. Uses the golden snapshot captured by Step01.

```bash
python3 <scripts>/symbol_differ.py \
  --snapshot $SNAPSHOT_PATH \
  --model $MODEL \
  --property $PROPERTY \
  --rmc-exit-code $PHASE0_EXIT_CODE \
  --rmc-stderr-log $OUTPUT_DIR/rmc/rmc_stderr.log \
  --output-json
```

Where `$SNAPSHOT_PATH` is the path emitted by `init_agent` in `shared_state.step01.snapshot_path`.

### Tier logic

| Tier | Condition | `hallucination_type` |
|------|-----------|----------------------|
| Tier 1 — Dead-code | Added state variable never referenced in `msgsrv` or `.property` | `dead_code` |
| Tier 2 — Reference | `phase0_exit_code == 5` AND property references symbol absent from model | `reference` |
| Clean | No offending symbols found | `null` |

```
phase3_passed = is_hallucination == false
```

If `phase3_passed == false`, route back to the agent that produced the hallucinating artifact:
- `hallucination_type == "dead_code"` → `mapping_agent` (Step04)
- `hallucination_type == "reference"` → `mapping_agent` (Step04) with RMC stderr diagnostics

## Output Contract (success)

```json
{
  "status": "ok",
  "source_file_path": "Rule-22",
  "verified": true,
  "rmc_exit_code": 0,
  "rmc_outcome": "verified",
  "rmc_output_dir": "/path/to/output",
  "vacuity_status": {
    "is_vacuous": false,
    "precondition_used": "!vessel_hasTarget",
    "secondary_exit_code": 4,
    "secondary_output_dir": "/path/to/secondary",
    "explanation": "NON-VACUOUS: negated property fails to compile — property exercises its precondition."
  },
  "mutation_score": 45.5,
  "mutation_detail": { "total": 11, "killed": 5, "survived": 6 },
  "open_assumptions": []
}
```

## Error Envelope

```json
{
  "status":  "error",
  "phase":   "step06",
  "agent":   "verification_agent",
  "message": "Human-readable description of failure"
}
```

Emit on: invalid paths, `run_rmc` internal exception, `check_vacuity` exception,
`MutationEngine` instantiation failure.

**Do not** emit an error envelope for non-zero `rmc_exit_code` — that is a valid
`verified=false` outcome, not an agent failure.

## Step06 Artifact Placement (MUST FOLLOW)

_Clarifies exactly where per-run artifacts land and which tree is the verification tree._

Set `$OUTPUT_DIR` to `output_policy.verification_paths(rule_id, run_id).run_dir`:
```
output/verification/<rule_id>/<run_id>/
```

Per-run artifacts written under `$OUTPUT_DIR`:
- `rmc_details.json` — raw RMC output (from `--output-file $OUTPUT_DIR/rmc_details.json`)
- `mutation_candidates.json` — generated mutants
- `mutation_killrun.json` — kill-run results
- `vacuity_check.json` — vacuity result (from `--output-file $OUTPUT_DIR/vacuity_check.json`)
- `scorecard.json` — per-run score (write after all phases complete)

After a passing run, publish the winner atomically to the canonical view:
```bash
# current_dir = output_policy.verification_paths(rule_id, run_id).current_dir
#             = output/verification/<rule_id>/current/
cp -rT "$OUTPUT_DIR" "$CURRENT_DIR"   # or rename if on the same filesystem
```

**Do not** write Step06 artifacts into `output/work/<rule_id>/runs/<run_id>/attempt-<N>/` —
that directory is the synthesis scratch space for Steps 04/05, not for verification outputs.

## Canonical Artifact Persistence (REQUIRED)

After all verification phases complete and the output contract is assembled, persist the canonical gate artifact atomically **before** returning output to the coordinator:

```bash
python skills/rebeca_tooling/scripts/artifact_writer.py \
  --rule-id <source_file_path> --step step06_verification_gate \
  --data '<output_contract_json>' [--base-dir output]
```

The `step06_verification_gate.json` artifact is required by Gate 0 and the FSM transition guard. It must contain `verified`, `rmc_exit_code`, `vacuity_status.is_vacuous`, and `mutation_score`.

## Output Patch (for coordinator)

- `workflow_summary.step06`
- `verification_report` (entire output contract)
- `single_rule_scorecard.failure_reasons` ← `rmc_outcome` when `verified=false`
- `single_rule_scorecard.remediation_hints` ← populated from `vacuity_status.explanation`
  and survived mutation list
