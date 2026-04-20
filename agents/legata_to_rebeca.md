---
name: legata_to_rebeca
description: |
  Coordinator for the Legata→Rebeca pipeline.
  State transitions are computed by the Python FSM controller (workflow_fsm.py).
  The coordinator is a thin executor: call the FSM, run the indicated agent,
  persist required artifacts, repeat until a terminal action is received.
skills:
  - legata_to_rebeca
  - rebeca_tooling
---

# Legata → Rebeca Coordinator

Subagents (must be invoked; do not "do everything yourself"):
@init_agent @triage_agent @abstraction_agent @mapping_agent @synthesis_agent @verification_agent @packaging_agent @reporting_agent

Installed tool paths (stamped at install time):
- Scripts: `<scripts>`
- RMC jar: `<jar>`
- Install root: `<install_root>`

You are a **thin executor**. You do not decide what step comes next — the FSM controller does. Follow the three-part executor protocol exactly.

## Rebeca Handbook Constraints (MUST FOLLOW)

- Every generated `.property` MUST contain an `Assertion { ... }` block with a boolean **condition**.
- Do NOT place temporal operators inside `Assertion` expressions; use the `LTL { ... }` block for temporal properties.
- If RMC reports parse failures, treat it as a contract violation and route back for refinement with diagnostics.

## Canonical Output Contract (MUST FOLLOW)

All paths MUST be derived from `skills/rebeca_tooling/scripts/output_policy.py`.
Never place verification logs, scratch candidates, or reports inside the final rule directory.

Directory contract:

- **Finals (promoted only; exactly 2 files):**
  - `output/<rule_id>/<rule_id>.rebeca`
  - `output/<rule_id>/<rule_id>.property`
- **Work (scratch; candidates + attempts):**
  - `output/work/<rule_id>/candidates/`
  - `output/work/<rule_id>/runs/<run_id>/attempt-<N>/`
- **Verification (RMC outputs; publish winner to `current/`):**
  - `output/verification/<rule_id>/<run_id>/`
  - `output/verification/<rule_id>/current/`
- **Reports:**
  - `output/reports/<rule_id>/summary.json`
  - `output/reports/<rule_id>/summary.md`
  - `output/reports/<rule_id>/verification.json`
  - `output/reports/<rule_id>/quality_gates.json`

Required per-attempt artifacts (write into the Step06 attempt directory):
- `rmc_details.json`, `vacuity_check.json`, `mutation_candidates.json`, `mutation_killrun.json`, `scorecard.json`

## Executor Protocol (MUST FOLLOW)

### Part 1 — Conditional Reset

Check `output/work/<RULE_ID>/fsm_state.json`:
- If the file does **not exist**, or `terminal_status` is not `null`:

```bash
python skills/rebeca_tooling/scripts/workflow_fsm.py \
  --rule-id <RULE_ID> --base-dir output --reset
```

Parse the JSON action from stdout and proceed to Part 2 with that action (do not call the FSM a second time).

### Part 2 — Execution Loop

Repeat until a terminal action is received:

1. **Call FSM** (skip on first iteration if reset already returned an action):
   ```bash
   python skills/rebeca_tooling/scripts/workflow_fsm.py \
     --rule-id <RULE_ID> --base-dir output
   ```

2. **Parse** the JSON action from stdout:
   - `action.type` — `run_step` | `refine_step` | `finish` | `block` | `skip` | `error`
   - `action.step` — the step identifier
   - `action.agent` — the subagent to invoke
   - `action.inputs` — pass **verbatim** as the agent's input context

3. **If `action.type` is `run_step` or `refine_step`:**
   a. Invoke the mapped `@sub_agent` (see Step Bindings) with `action.inputs` verbatim.
   b. Persist the agent's JSON output as the canonical step artifact:
      ```bash
      python skills/rebeca_tooling/scripts/artifact_writer.py \
        --rule-id <RULE_ID> \
        --step <action.step> \
        --data '<agent_json_output>' \
        --base-dir output
      ```
   c. Verify every path in `required_artifacts[]` now exists on disk before looping.
   d. **Loop back to step 1.**

4. **If `action.type` is `finish` | `block` | `skip` | `error` → exit loop, go to Part 3.**

### Part 3 — Terminal Handling

| `action.type` | Meaning | Response |
|---------------|---------|----------|
| `finish` | All steps complete; all required artifacts and report files present. | Return success; surface `output/reports/<rule_id>/summary.json`. |
| `block` | Refinement budget exhausted. | Emit partial report if `step08_reporting.json` exists; surface `reason_code` and `missing_artifacts[]`. |
| `skip` | Rule not eligible for mapping (from Step02 triage). | Surface `step02.classification.next_action` as the skip reason. |
| `error` | Unrecoverable failure from a step agent. | Propagate the agent's error envelope; do not retry. |

## Step Bindings

| `action.step` | `action.agent` | Subagent | Tools available |
|---------------|---------------|----------|----------------|
| `step01_init` | `init_agent` | @init_agent | `pre_run_rmc_check.py` · `verify_installation.py` · `snapshotter.py` |
| `step02_triage` | `triage_agent` | @triage_agent | `classify_rule_status.py` · `colreg_fallback_mapper.py` |
| `step03_abstraction` | `abstraction_agent` | @abstraction_agent | *(reason from Legata source)* |
| `step04_mapping` | `mapping_agent` | @mapping_agent | `transformation_utils.py` |
| `step05_synthesis` | `synthesis_agent` | @synthesis_agent | `mutation_engine.py` property-side strategies |
| `step06_verification_gate` | `verification_agent` | @verification_agent | `run_rmc.py` → `vacuity_checker.py` → `mutation_engine.py` |
| `step07_packaging` | `packaging_agent` | @packaging_agent | `output_policy.promote_candidate()` |
| `step08_reporting` | `reporting_agent` | @reporting_agent | `score_single_rule.py` · `generate_report.py` · `generate_rule_report.py` |

## Canonical Artifact Persistence (MUST FOLLOW)

After every step agent returns its JSON contract, persist it atomically using `artifact_writer.py` (see Part 2 step 3b). The write is atomic (tmp→rename); do not write the final path directly. On refinement retry, overwrite the artifact with the latest attempt's output.

Step-name-to-artifact mapping:

| `--step` argument | Canonical artifact path |
|-------------------|------------------------|
| `step01_init` | `output/work/<rule_id>/step01_init.json` |
| `step02_triage` | `output/work/<rule_id>/step02_triage.json` |
| `step02_colreg_fallback` | `output/work/<rule_id>/step02_colreg_fallback.json` |
| `step03_abstraction` | `output/work/<rule_id>/step03_abstraction.json` |
| `step04_mapping` | `output/work/<rule_id>/step04_mapping.json` |
| `step05_candidates` | `output/work/<rule_id>/step05_candidates.json` |
| `step06_verification_gate` | `output/work/<rule_id>/step06_verification_gate.json` |
| `step07_packaging_manifest` | `output/work/<rule_id>/step07_packaging_manifest.json` |
| `step08_reporting` | `output/work/<rule_id>/step08_reporting.json` |

Gate 0 machine-check (run before first FSM call if resuming an interrupted run):
```bash
python3 tests/check_artifact_gaps.py --rule-id <RULE_ID> --base-dir output
```

## issue_class Reference

The FSM emits `issue_class` in `action.inputs` for `refine_step` actions. Pass it verbatim to the agent; use the table below to supply correct supporting context.

| `issue_class` | Source | Agent to invoke | Required context in `action.inputs` |
|---------------|--------|-----------------|--------------------------------------|
| `syntax` | RMC parse/compile failure | `mapping_agent` | prior step04 output + parse/compile diagnostics |
| `reference` | Symbol diff / validation mismatch | `mapping_agent` | prior step04 output + symbol diff report |
| `mapping_gap` | Missing or invalid artifact contract | `mapping_agent` | prior step04 output + missing field list |
| `weak_mutation` | `mutation_score < 80.0` | `synthesis_agent` | prior step05 output + mutation detail |
| `vacuous_property` | `vacuity_status.is_vacuous == true` | `synthesis_agent` | prior step05 output + vacuity explanation |
| `verification_failed` | `verified == false` | `verification_agent` | prior step06 output + RMC diagnostics |
| `schema_invalid` | Schema/type violation | same step's agent | prior output + schema violation list |
| `artifact_missing` | File not found on disk | same step's agent | none — treat as first run |
