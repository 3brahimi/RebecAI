---
name: legata_to_rebeca
description: |
  Transforms a Legata rule into a verified Rebeca actor model.
  Runs Steps 01–08 in sequence: init → triage → abstract → map →
  synthesize → verify → package → report.
skills:
  - legata_to_rebeca
  - rebeca_tooling
---

# Legata → Rebeca Agent

You execute all eight steps yourself in sequence. There are no subagents.

## Required Inputs

Before starting, confirm the caller has provided all five values. If any are
missing, print which ones are absent and stop.

| Input | Description |
|---|---|
| `rule_id` | Short identifier, e.g. `Rule-22` |
| `legata_input` | Path to the Legata `.txt` rule file |
| `reference_model` | Path to the reference `.rebeca` file (used as template in Step 04) |
| `reference_property` | Path to the reference `.property` file (used as template in Step 04) |
| `output_dir` | Where artifacts are written; default: `output/<rule_id>` |

If `output_dir` was not provided, set it to `output/<rule_id>` now before
proceeding.

## Script Location
All dumb tools live in the `rebeca_tooling` skill. Resolve their location before any step:

Agent Installation Path: `<install_root>`
Scripts Path: `<scripts>`
RMC JAR Path: `<jar>`

## Steps

### Step 01 — Init

Provision the toolchain and verify the installation is healthy.

```
python3 <scripts>/pre_run_rmc_check.py
python3 <scripts>/verify_installation.py <install_root>
```

Check: both commands exit 0. If not, stop.

---

### Step 02 — Triage

Classify the rule's formalization status.

```
python3 <scripts>/classify_rule_status.py \
  --legata-path <legata_input> \
  --output-json
```

Check: `classification.status` is `formalized` or `not-formalized` to proceed.
If status is `incomplete`, `incorrect`, or `todo-placeholder`, report the
defects and stop.

---

### Step 03 — Abstract

Read `<legata_input>`. Use `<reference_model>` and `<reference_property>` as
structural context. Extract actor names (PascalCase) and state variables
(camelCase) following rebeca-handbook naming conventions.

Check: at least one actor and one state variable were found. If either list is
empty, report which is missing and stop.

---

### Step 04 — Map

Generate `<rule_id>.rebeca` and `<rule_id>.property` using
`transformation_utils` helpers. Use `<reference_model>` and
`<reference_property>` as templates for structure and syntax. Write both files
to `<output_dir>`.

```
python3 <scripts>/transformation_utils.py \
  --rule-id <rule_id> \
  --reference-model <reference_model> \
  --reference-property <reference_property> \
  --output-dir <output_dir>
```

Check: `<output_dir>/<rule_id>.rebeca` and `<output_dir>/<rule_id>.property`
both exist and are non-empty. If a parse or compile error is reported, attempt
one correction before stopping.

---

### Step 05 — Synthesize

Generate candidate property variants.

```
python3 <scripts>/mutation_engine.py \
  --rule-id <rule_id> \
  --property <output_dir>/<rule_id>.property \
  --output-file <output_dir>/<rule_id>_candidates.json
```

Check: `<output_dir>/<rule_id>_candidates.json` exists and is non-empty JSON.

---

### Step 06 — Verify

Run the model checker, then the vacuity check, then mutation scoring.

```
python3 <scripts>/run_rmc.py \
  --jar <jar> \
  --model <output_dir>/<rule_id>.rebeca \
  --property <output_dir>/<rule_id>.property \
  --output-dir <output_dir>/rmc-out \
  --timeout-seconds 120

python3 <scripts>/vacuity_checker.py \
  --jar <jar> \
  --model <output_dir>/<rule_id>.rebeca \
  --property <output_dir>/<rule_id>.property \
  --output-dir <output_dir>/rmc-out \
  --rule-id <rule_id> \
  --output-json

python3 <scripts>/mutation_engine.py \
  --rule-id <rule_id> \
  --model <output_dir>/<rule_id>.rebeca \
  --property <output_dir>/<rule_id>.property \
  --run-with-jar <jar> \
  --run-with-model <output_dir>/<rule_id>.rebeca \
  --run-with-property <output_dir>/<rule_id>.property \
  --output-file <output_dir>/mutation_results.json
```

Check: `rmc_exit_code == 0`, `is_vacuous == false`, `mutation_score >= 80`.
See failure handling below if any check fails.

---

### Step 07 — Package

Confirm the model, property, and RMC logs are present in `<output_dir>`.

```
<output_dir>/<rule_id>.rebeca
<output_dir>/<rule_id>.property
<output_dir>/rmc-out/*.log
```

Check: all three file types are present. If any are missing, stop.

---

### Step 08 — Report

Score the rule and generate the report.

```
python3 <scripts>/score_single_rule.py \
  --rule-id <rule_id> \
  --verify-status pass \
  --output-file <output_dir>/reports/<rule_id>/scorecard.json

python3 <scripts>/generate_report.py \
  --input-scores <output_dir>/reports/<rule_id>/scorecard.json \
  --output-dir <output_dir>/reports/<rule_id> \
  --format both
```

Outputs: `summary.json` and `summary.md` in `<output_dir>/reports/<rule_id>/`.

---

## Failure Handling

If any step exits non-zero or produces missing or empty output: write an error
summary to `<output_dir>/reports/<rule_id>/error.json`, print the failure to
the user, and stop. Do not proceed to the next step.

Step 04 parse or compile error: attempt one correction of the generated
`.rebeca` or `.property` file before stopping.

Step 06 vacuity failure: the property is structurally valid but trivially true.
Score the rule as Conditional and stop.

Step 06 mutation score below 80: score the rule as Conditional and stop.

## Output Summary

After Step 08, print:

```
Rule:   <rule_id>
Status: Pass | Conditional | Fail
Report: <output_dir>/reports/<rule_id>/summary.md
```
