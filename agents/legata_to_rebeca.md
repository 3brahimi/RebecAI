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
mkdir -p "<output_dir>/<rule_id>"
cp "<reference_model>" "<output_dir>/<rule_id>/<rule_id>.rebeca"

# If a reference property path was provided and exists, copy it.
# Otherwise create a minimal placeholder property so Init doesn't fail.
if [ -n "<reference_property>" ] && [ -f "<reference_property>" ]; then
  cp "<reference_property>" "<output_dir>/<rule_id>/<rule_id>.property"
else
  cat > "<output_dir>/<rule_id>/<rule_id>.property" <<'PROPERTY'
property{
    define{
        // Here goes the definition of Boolean Atomic Propositions
        // ap1 = (rebec.statevar == value);
        // ap2 = (rebec.statevar >= value);
    }

    Assertion{
        // Here goes the assertion of Boolean Invariants
        // invariant1: !ap1 || ap2;
    }
}
PROPERTY
fi
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
- `rule_id: "<rule_id>"`
- `abstraction_summary` with:
  - `naming_contract` — object with `reactive_class_style`, `state_var_style`, `instance_style`, `define_alias_style`, `assertion_name_style`
  - `actor_map` — **array** of `{legata_actor, rebeca_class, rebeca_instance}` (no duplicates, order preserved)
  - `variable_map` — **array** of `{legata_concept, rebeca_class, rebeca_statevar, rebeca_type, rebeca_init_value (array), is_new, legata_var?, legata_value?, bounds?}` where:
    - `rebeca_init_value` is always an array: 1 element = deterministic, 2+ = non-deterministic (OWA)
    - `is_new` is boolean: `false` = existing statevar, `true` = new statevar to add
- `open_assumptions` — array of strings (may be empty)

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
- `rule_id: "<rule_id>"`
- `concept_mapping` with **all four keys present**:
  - `statevar_patches` — **non-empty** array of `{reactiveclass, add_statevars: [{type, name, init}]}` where `init` uses Rebeca OWA syntax `?(val1, val2)` for non-deterministic or a plain value for deterministic
  - `queue_size_patches` — array of `{reactiveclass, queue_size}` (may be empty)
  - `define_patches` — array of `{ap, expr}` (may be empty if no properties needed)
  - `assertion_lines` — **non-empty** array of strings, each of the form `RuleN: !condAP || exclAP || assureAP;` using only AP names defined in `define_patches`
- `open_assumptions` — array of strings (may be empty)

**Validation rules:**
- If `concept_mapping` is missing, is a flat dict, has `assertion_line` (singular), or is missing any of the four keys: stop with `"mapping_agent returned wrong schema"`
- At least one of `statevar_patches` or `assertion_lines` must be non-empty (rule must add something)

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
- `rule_id: "<rule_id>"`
- `patched_files` — object with **both keys** present:
  - `model_path` — path string ending in `.rebeca`, points to `<output_dir>/<rule_id>/<rule_id>.rebeca`
  - `property_path` — path string ending in `.property`, points to `<output_dir>/<rule_id>/<rule_id>.property`

**Important:** synthesis_agent applies **surgical patches only** — it reads the existing `.rebeca` and `.property` files verbatim, applies the four patch types from `concept_mapping` (add statevars, update queue sizes, add define aliases, add assertion lines), and writes the modified files. It does **NOT** rewrite the entire file content. All existing class names, message servers, `main {}`, `LTL {}`, and comments are preserved.

If the output is missing `patched_files` or its keys, is malformed, or contains wrong paths: stop with error `"synthesis_agent returned wrong schema"`.

Persist the full JSON output regardless of status:
```bash
python <scripts>/artifact_writer.py \
  --rule-id  <rule_id> \
  --step     step04_synthesis \
  --data     '<full agent JSON output>' \
  --base-dir <output_dir>
```

On `status: error` or schema mismatch → stop and return the persisted error to the caller.
On `status: ok` → the synthesis_agent has already written the patched files in place:
- `<output_dir>/<rule_id>/<rule_id>.rebeca`
- `<output_dir>/<rule_id>/<rule_id>.property`

Proceed immediately to Step 05.

---

### Step 05 — Verification (`verify_gate.py`)

`verify_gate.py` writes its own artifact — no separate `artifact_writer.py` call needed.

```bash
python <scripts>/verify_gate.py \
  --rule-id    <rule_id> \
  --model      <output_dir>/<rule_id>/<rule_id>.rebeca \
  --property   <output_dir>/<rule_id>/<rule_id>.property \
  --jar        <jar> \
  --output-dir <output_dir>/verification/<rule_id> \
  --base-dir   <output_dir>
```

> **Optional:** Append `--vacuity` to enable vacuity checking; append `--mutation` to enable mutation-based testing. Both are off by default.

Stdout is a compact status line: `{"status":"ok","passes_gate":<bool>,"artifact":"<path>"}`.

**FAIL-FAST:**
- If exit code is non-zero or `passes_gate` is `false`: **STOP. Do NOT run Step 06 or Step 07.** Return `{"status":"error","step":"step05_verification_gate","passes_gate":false}` to the caller.
- Only if `passes_gate` is `true`: keep `rmc_exit_code`, `vacuity_status.is_vacuous`, `mutation_score` (read from the artifact path in stdout) and proceed to Step 06.

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

Mutation and vacuity are either both disabled (no args in Step 05, since `--no-vacuity` and `--no-mutation` are default) or both enabled (both passed `--vacuity` and `--mutation` in Step 05).

Run these three commands in sequence. On any failure: stop and return the error to the caller.

**Step 07a — Score** (`score_rule.py`)

Default (both disabled):
```bash
python <scripts>/score_rule.py \
  --rule-id       <rule_id> \
  --rmc-exit-code <step05_verification_gate.rmc_exit_code> \
  --output-dir    <output_dir>
```

With vacuity and mutation enabled:
```bash
python <scripts>/score_rule.py \
  --rule-id        <rule_id> \
  --rmc-exit-code  <step05_verification_gate.rmc_exit_code> \
  --is-vacuous     <step05_verification_gate.vacuity_status.is_vacuous> \
  --mutation-score <step05_verification_gate.mutation_score> \
  --output-dir     <output_dir>
```

`score_rule.py` writes the scorecard to `<output_dir>/work/<rule_id>/step07_reporting.json` automatically.

**Step 07b — Aggregate Report** (`generate_report.py`)

```bash
python <scripts>/generate_report.py \
  --input-scores <output_dir>/work/<rule_id>/step07_reporting.json \
  --output-dir   <output_dir>/reports/<rule_id> \
  --format both
```

**Step 07c — Per-Rule Comprehensive Report** (`generate_rule_report.py`)

```bash
python <scripts>/generate_rule_report.py \
  --rule-dir   <output_dir>/<rule_id> \
  --output-dir <output_dir>/reports/<rule_id>
```

On any failure → stop and propagate stderr.

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
