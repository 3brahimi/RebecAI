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

## Required Inputs

The coordinator expects these inputs when invoked:

```
rule_id:            <rule identifier, e.g. Rule-22>
legata_input:       <path to .legata source file>
reference_model:    <path to existing .rebeca file to start from>
reference_property: <path to existing .property file to start from>
output_dir:         <output directory, e.g. output/Rule-22>
```

**Critical workflow invariant:** The `<reference_model>` and `<reference_property>` are the **starting points** for refinement. Step01 copies them to `<output_dir>/<rule_id>.rebeca` and `<output_dir>/<rule_id>.property`, and all subsequent steps refine these files **in place** until they pass verification.

Subagents (LLM agents; invoked only for Steps 03, 04, 05):
1. @abstraction_agent
2. @mapping_agent
3. @synthesis_agent

**Never read `.py` files under `<scripts>/`.** Run them. Their CLI contracts are documented in `rebeca_tooling` SKILL.md.

Installed tool paths:
- Scripts: `<scripts>`
- RMC jar: `<jar>`
- Install root: `<install_root>`
- Agents: `<agents>`
- Skills: `<skills>`

You are a **thin executor**. You do not decide what step comes next — the FSM controller does. Follow the three-part executor protocol exactly.

## Direct Script Steps

Steps 01, 02, 06, 07, 08 are deterministic — the coordinator runs their scripts directly.
No LLM agent is invoked.

This coordinator is intentionally a **thin executor**: it documents only dispatch (what to run) and does not embed full CLI flags.
Authoritative CLI contracts live in `rebeca_tooling` SKILL.md under:
`## Module Reference` → **Direct Exec Step CLIs (Coordinator Reference)**.

For the canonical mapping from `action.step` → `action.agent` (and which script that implies), see **Step Bindings** below.

## FSM Invocation Policy

**Normative interface:** call `workflow_fsm.py` directly (as shown in the Executor Protocol below). This is the only sanctioned coordinator boundary.

- `workflow_fsm.py` is the canonical FSM controller: a pure decision engine that reads artifacts from disk and prints exactly one JSON action to stdout. Coordinators MUST call it directly.

## Output Contract

**Global invariants:** All paths derive from `output_policy.py` — never place artifacts outside these directories. Every `.property` must contain an `Assertion { ... }` block with a boolean condition; use `LTL { ... }` for temporal properties. On RMC parse failure, treat as a contract violation and route back for refinement with diagnostics.

Directory contract:

- **Finals (promoted only; exactly 2 files):**
  - `output/<rule_id>/<rule_id>.rebeca`
  - `output/<rule_id>/<rule_id>.property`
- **Work (scratch; candidates + attempts):**
  - `output/work/<rule_id>/candidates/`
  - `output/work/<rule_id>/runs/<run_id>/attempt-<N>/`
- **Verification** (RMC outputs; publish winner to `current/`):
  - `output/verification/<rule_id>/<run_id>/` — Step06 writes here: `rmc_details.json`, `vacuity_check.json`, `mutation_candidates.json`, `mutation_killrun.json`, `scorecard.json` (via `output_policy.verification_paths(rule_id, run_id).run_dir`)
  - `output/verification/<rule_id>/current/` — winning run published after successful verification (via `.current_dir`)
  - Note: `output/work/<rule_id>/runs/<run_id>/attempt-<N>/` is synthesis scratch (Steps 04/05) — distinct from the verification tree.
- **Reports:**
  - `output/reports/<rule_id>/summary.json`, `summary.md`, `verification.json`, `quality_gates.json`

## Executor Protocol

_Three-part loop: conditional reset → execution loop → terminal handler. Do not skip parts._

### Part 1 — Conditional Reset

Check `output/work/<RULE_ID>/fsm_state.json`:
- If the file does **not exist**, or `terminal_status` is not `null`:

```bash
# CRITICAL: Copy reference files to output_dir as starting points for refinement
mkdir -p <output_dir>
cp <reference_model> <output_dir>/<rule_id>.rebeca
cp <reference_property> <output_dir>/<rule_id>.property

# Then reset FSM
python <scripts>/workflow_fsm.py \
  --rule-id <RULE_ID> --base-dir output --reset
```

**Important:** The reference files MUST be copied before the first FSM call. All subsequent steps (abstraction, mapping, synthesis, verification) will refine these files in place.

Parse the JSON action from stdout and proceed to Part 2 with that action (do not call the FSM a second time).

### Part 2 — Execution Loop

Repeat until a terminal action is received:

1. **Call FSM** (skip on first iteration if reset already returned an action):
   ```bash
   python <scripts>/workflow_fsm.py \
     --rule-id <RULE_ID> --base-dir output
   ```

2. **Parse** the JSON action from stdout:
   - `action.type` — `run_step` | `refine_step` | `finish` | `block` | `skip` | `error`
   - `action.step` — the step identifier (`"none"` for terminal actions)
   - `action.agent` — the subagent to invoke (`"none"` for terminal actions)
   - `action.inputs` — pass **verbatim** as the agent's input context

   Schema sources (machine-verifiable):
   - `<scripts>/schemas/workflow-fsm-action.schema.json`
   - `<scripts>/step_schemas.py` key `"fsm_action"`

   Terminal constraint (enforced by schema `allOf`): when `action.type` is `finish`, `block`, or `skip`, the schema requires `action.step = "none"` and `action.agent = "none"`.

3. **If `action.type` is `run_step` or `refine_step`:**

  Dispatch on `action.agent`:

  **Branch A — Direct script steps** (`action.agent` ∈ {`init_exec`, `triage_exec`,
  `verification_exec`, `packaging_exec`, `reporting_exec`}):
  a. Run the script identified by the Step Bindings mapping for this `action.step`, mapping
    `action.inputs` fields to CLI arguments (CLI contract: `rebeca_tooling/SKILL.md`).
  b. Capture stdout as the step artifact JSON.
  c. If exit code is non-zero, treat stdout as an error envelope → go to Part 3 (`error`).

  **Branch B — LLM subagent steps** (`action.agent` ∈ {`abstraction_agent`,
  `mapping_agent`, `synthesis_agent`}):
  a. Invoke the subagent specified in `action.agent` with `action.inputs` verbatim.
  b. Capture the agent's JSON output as the step artifact JSON.

  **Both branches then:**
  d. Persist the artifact:
    ```bash
    python <scripts>/artifact_writer.py \
      --rule-id <RULE_ID> \
      --step <artifact_step_name_for_action_step> \
      --data '<step_artifact_json>' \
      --base-dir output
    ```
    Note: `action.step` enum and artifact filename can differ — see Canonical Artifact Persistence.
  e. Verify every path in `required_artifacts[]` now exists on disk before looping.
  f. **Loop back to step 1.**

4. **If `action.type` is `finish` | `block` | `skip` | `error` → exit loop, go to Part 3.**

### Part 3 — Terminal Handling

Terminal actions end the executor loop and MUST NOT invoke another step agent. Each type has one deterministic response — do not deviate.

- **`finish`** — All steps complete; all required artifacts and report files present.
  → Return success; surface `output/reports/<rule_id>/summary.json`.
- **`block`** — Refinement budget exhausted.
  → Emit partial report if `step08_reporting.json` exists; surface `reason_code` and `missing_artifacts[]`.
- **`skip`** — Rule not eligible for mapping (from Step02 triage).
  → Surface `step02.classification.next_action` as the skip reason.
- **`error`** — Unrecoverable failure from a step agent.
  → Propagate the agent's error envelope; do not retry.

## Step Bindings

The FSM `action.step` field identifies the step enum, and `action.agent` specifies execution mode. Direct steps run a script; LLM
steps invoke a subagent specified in `action.agent`. Do not remap.

CLI contracts for direct steps are in `<skills>/rebeca_tooling/SKILL.md` → **Direct Exec Step CLIs** (line 379).

- `step01_init` → `init_exec` (direct: no standalone CLI — handled by coordinator setup)
- `step02_triage` → `triage_exec` (direct: `classify_rule_status.py`; `<skills>/rebeca_tooling/SKILL.md` line 383)
- `step03_abstraction` → `abstraction_agent` (LLM subagent)
- `step04_mapping` → `mapping_agent` (LLM subagent)
- `step05_synthesis` → `synthesis_agent` (LLM subagent; artifact name: `step05_candidates` ≠ enum)
- `step06_verification_gate` → `verification_exec` (direct: `verify_gate.py`; `<skills>/rebeca_tooling/SKILL.md` line 393)
- `step07_packaging` → `packaging_exec` (direct: no standalone CLI — coordinator copies finals to output dir)
- `step08_reporting` → `reporting_exec` (direct: `score_single_rule.py | generate_report.py`; `<skills>/rebeca_tooling/SKILL.md` line 415)

## Canonical Artifact Persistence

The executor persists step artifacts via `artifact_writer.py`. The FSM's `action.step` enum and the persisted artifact name can differ intentionally for a small set of steps (e.g., `step05_synthesis` → `step05_candidates`, `step07_packaging` → `step07_packaging_manifest`).

Anti-drift rule (canonical runtime sources that MUST agree):
- `workflow_fsm` (`workflow_fsm._PIPELINE` step enums + artifact names)
- `output_policy` (the allowed artifact name set enforced by `output_policy.step_artifact_path`)

In the executor loop, use an explicit mapping placeholder rather than passing `action.step` raw:
```bash
python <scripts>/artifact_writer.py \
  --rule-id <RULE_ID> \
  --step <artifact_step_name_for_action_step> \
  --data '<step_artifact_json>' \
  --base-dir output
```

Write is atomic (tmp→rename).

## issue_class Reference

The FSM emits `issue_class` in `action.inputs` for `refine_step` actions. Pass `action.inputs` verbatim to the subagent specified in `action.agent` — the subagent will interpret the issue class and request the appropriate prior context from you.
