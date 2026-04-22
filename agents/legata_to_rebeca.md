---
name: legata_to_rebeca
description: |
  Coordinator for the Legata→Rebeca pipeline.
  Runs a fixed linear sequence of steps: abstraction → mapping → synthesis → verification → packaging → reporting.
  Fail-fast: any step failure stops the pipeline immediately.
tools: ["*"]
skills:
  - legata_to_rebeca
  - rebeca_tooling
---

# Legata → Rebeca Coordinator

## Required Inputs

```
rule_id:            <rule identifier, e.g. Rule-22>
legata_input:       <path to .legata source file>
reference_model:    <path to existing .rebeca file to start from>
reference_property: <path to existing .property file to start from>
output_dir:         <base output directory, e.g. output>
```

Installed tool paths (substituted by the harness at invocation time):
- Scripts: `<scripts>`
- RMC jar: `<jar>`
- Agents: `<agents>`
- Skills: `<skills>`

CLI contracts for all scripts are in `rebeca_tooling` SKILL.md. **Never read `.py` files — run them.**

## Subagent Invocation

Steps 02, 03, and 04 delegate to named subagents using `@agent_name` syntax. **Never invent or simplify a subagent's output schema** — the exact JSON contract in each agent file is what downstream steps depend on.

---

## Pipeline

Run these steps in order. On any failure: persist the error artifact, then stop and return the error to the caller.

---

### Step 01 — Initialise

**Do NOT call `artifact_writer.py` for this step. No JSON artifact is written.**

```bash
mkdir -p <output_dir>/<rule_id>
cp <reference_model>    <output_dir>/<rule_id>/<rule_id>.rebeca
cp <reference_property> <output_dir>/<rule_id>/<rule_id>.property
```

If either `cp` fails, stop: `"Init failed: could not copy reference files"`.
Proceed directly to Step 02.

---

### Step 02 — Abstraction (`abstraction_agent`)

```
@abstraction_agent

rule_id:       <rule_id>
legata_input:  <legata_input>
output_dir:    <output_dir>
```

Validate the output contains exactly this structure before persisting — if not, treat as error:
- `status: "ok"`
- `abstraction_summary.actor_map` — object keyed by class name, each value has `queue_size` (int) and `source` (string)
- `abstraction_summary.variable_map` — object keyed by camelCase var name, each value has `type`, `default`, `source`

Persist the full JSON output regardless of status:
```bash
python <scripts>/artifact_writer.py \
  --rule-id  <rule_id> \
  --step     step02_abstraction \
  --data     '<full agent JSON output>' \
  --base-dir <output_dir>
```

On `status: error` or schema mismatch → stop and return the persisted error to the caller.
On `status: ok` → keep `abstraction_summary` in memory for Step 03.

---

### Step 03 — Mapping (`mapping_agent`)

```
@mapping_agent

rule_id:              <rule_id>
legata_input:         <legata_input>
output_dir:           <output_dir>
abstraction_summary:  <step02_abstraction.abstraction_summary>
```

Validate the output contains exactly this structure before persisting — if not, treat as error:
- `status: "ok"`
- `concept_mapping.statevar_patches` — array of `{reactiveclass, add_statevars: [{type, name, default}]}`
- `concept_mapping.queue_size_patches` — array of `{reactiveclass, queue_size}`
- `concept_mapping.define_patches` — array of `{alias, expr}`
- `concept_mapping.assertion_lines` — non-empty array of strings, each of the form `RuleN: !alias || alias;`

If `concept_mapping` is a flat name→name dict, or has `assertion_line` (singular) instead of `assertion_lines` (array), or is missing any of the four keys, it is wrong — stop with error `"mapping_agent returned wrong schema"`.

Persist the full JSON output regardless of status:
```bash
python <scripts>/artifact_writer.py \
  --rule-id  <rule_id> \
  --step     step03_mapping \
  --data     '<full agent JSON output>' \
  --base-dir <output_dir>
```

On `status: error` or schema mismatch → stop and return the persisted error to the caller.
On `status: ok` → keep `concept_mapping` in memory for Step 04.

---

### Step 04 — Synthesis (`synthesis_agent`)

```
@synthesis_agent

rule_id:              <rule_id>
output_dir:           <output_dir>
abstraction_summary:  <step02_abstraction.abstraction_summary>
concept_mapping:      <step03_mapping.concept_mapping>
legata_text:          <raw content of legata_input file>
```

Validate the output contains exactly this structure before persisting — if not, treat as error:
- `status: "ok"`
- `patched_files.model_path` — path string ending in `.rebeca`
- `patched_files.property_path` — path string ending in `.property`

If the output is missing `patched_files`, it is wrong — stop with error `"synthesis_agent returned wrong schema"`.

Persist the full JSON output regardless of status:
```bash
python <scripts>/artifact_writer.py \
  --rule-id  <rule_id> \
  --step     step04_synthesis \
  --data     '<full agent JSON output>' \
  --base-dir <output_dir>
```

On `status: error` or schema mismatch → stop and return the persisted error to the caller.
On `status: ok` → the synthesis_agent writes the patched `<output_dir>/<rule_id>/<rule_id>.rebeca` and `.property` directly. Proceed to Step 05.

---

### Step 05 — Verification (`verify_gate.py`)

```bash
python <scripts>/verify_gate.py \
  --rule-id    <rule_id> \
  --model      <output_dir>/<rule_id>/<rule_id>.rebeca \
  --property   <output_dir>/<rule_id>/<rule_id>.property \
  --jar    <jar> \
  --output-dir <output_dir>/verification/<rule_id>
```

Persist stdout regardless of outcome:
```bash
python <scripts>/artifact_writer.py \
  --rule-id  <rule_id> \
  --step     step05_verification_gate \
  --data     '<verify_gate.py stdout>' \
  --base-dir <output_dir>
```

**FAIL-FAST — CHECK THIS BEFORE DOING ANYTHING ELSE:**
Parse `passes_gate` from the JSON output above.
- If `passes_gate` is `false` (or the JSON is missing): **STOP IMMEDIATELY. Do NOT run Step 06 or Step 07.** Return the persisted artifact to the caller as the final result.
- Only if `passes_gate` is `true`: keep `rmc_exit_code`, `vacuity_status.is_vacuous`, `mutation_score` and proceed to Step 06.

---

### Step 06 — Packaging

```bash
python <scripts>/artifact_writer.py \
  --rule-id  <rule_id> \
  --step     step06_packaging_manifest \
  --data     '{"status":"ok","rule_id":"<rule_id>","finals":["<output_dir>/<rule_id>/<rule_id>.rebeca","<output_dir>/<rule_id>/<rule_id>.property"]}' \
  --base-dir <output_dir>
```

---

### Step 07 — Reporting

```bash
python <scripts>/score_single_rule.py \
  --rule-id        <rule_id> \
  --rmc-exit-code  <step05_verification_gate.rmc_exit_code> \
  --is-vacuous     <step05_verification_gate.vacuity_status.is_vacuous> \
  --mutation-score <step05_verification_gate.mutation_score> \
  --output-json \
| python <scripts>/generate_report.py \
  --output-dir <output_dir>/reports/<rule_id>
```

`score_single_rule.py` does NOT accept `--output-dir`. Use `--output-json` to pipe its scorecard JSON to `generate_report.py`. `generate_report.py` accepts `--output-dir`.

On failure → stop and propagate stderr.

On success → persist stdout:
```bash
python <scripts>/artifact_writer.py \
  --rule-id  <rule_id> \
  --step     step07_reporting \
  --data     '<generate_report.py stdout>' \
  --base-dir <output_dir>
```

Return `<output_dir>/reports/<rule_id>/summary.json` to the caller.

---

## Output Directory Layout

```
<output_dir>/
  <rule_id>/
    <rule_id>.rebeca            ← final model
    <rule_id>.property          ← final property
  verification/<rule_id>/       ← verify_gate.py outputs
  reports/<rule_id>/            ← summary.json, summary.md, verification.json, quality_gates.json
  work/<rule_id>/
    step02_abstraction.json
    step03_mapping.json
    step04_synthesis.json
    step05_verification_gate.json
    step06_packaging_manifest.json
    step07_reporting.json
```
