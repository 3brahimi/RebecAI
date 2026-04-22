---
name: legata_to_rebeca_unified
description: |
  Refines an existing .rebeca and .property pair until they pass RMC verification.
  Uses the Legata source as semantic ground truth. Emits a score report.
---

# Legata → Rebeca: Refine and Verify

**The mission:** take `reference_model` and `reference_property`, refine them until they
pass RMC verification, and write the final files to `output_dir`.

---

## Installed tool paths
- Scripts: `<scripts>`
- RMC jar: `<jar>`

## Interface

### Inputs from coordinator invocation
```
<rule_id>:            <rule identifier, e.g. Rule-22>
<legata_input>:       <path to .legata source file>
<reference_model>:    <path to existing .rebeca file to start from>
<reference_property>: <path to existing .property file to start from>
<output_dir>:         <output directory, e.g. output/Rule-22>
```

### Outputs to coordinator
- Written and refined in place:
  - `<output_dir>/<rule_id>.rebeca`
  - `<output_dir>/<rule_id>.property`
- Written once at end of successful run:
  - `<output_dir>/reports/scorecard.json`
  - `<output_dir>/reports/summary.json`

---

## Phase 1 — Eligibility check

```bash
python3 <scripts>/classify_rule_status.py \
  --legata-path <legata_input> \
  --output-json
```

If `status` is `not-formalized` or `todo-placeholder` → stop:
```
SKIP: <rule_id> — <next_action>
```

---

## Phase 2 — Read and copy reference files

Copy the reference files to the working locations:
```bash
mkdir -p output_dir
cp <reference_model>    <output_dir>/<rule_id>.rebeca
cp <reference_property> <output_dir>/<rule_id>.property
```

Then read both files and `<legata_input>`. Understand:
- What the Legata rule requires (actors, conditions, exclusions, assurances)
- What the reference files currently express
- Where they diverge from the Legata semantics

Use this understanding in Phase 3 when making corrections.

### Legata → Rebeca semantics reference

Every Legata rule: `condition ∧ ¬exclude → assure` = `¬condition ∨ exclude ∨ assure`

| Legata section | Role in `.property` assertion |
|----------------|-------------------------------|
| `Condition`    | Negated: `!condition \|\|`    |
| `Exclude`      | Positive: `exclude \|\|`      |
| `Assure`       | Positive, ANDed: `(a1 && a2)` |

Property structure:
```property
property {
  define {
    alias = (instance.statevar op value);
  }
  Assertion {
    RuleName: !condition || exclude || (assurance1 && assurance2);
  }
}
```

Model structure:
```rebeca
reactiveclass ClassName(10) {
  statevars { type name; }
  ClassName() { name = default; }
  msgsrv tick() { }
}
main { ClassName instance():(); }
```

---

## Phase 3 — Verify and refine (max 3 attempts)

Run RMC against the working files. If they fail, edit them in place using the Legata as
ground truth for what the semantics should be.

### Run verification gate

```bash
python3 <scripts>/verify_gate.py \
  --jar        <jar> \
  --model      <output_dir>/<rule_id>.rebeca \
  --property   <output_dir>/<rule_id>.property \
  --rule-id    <rule_id> \
  --output-dir <output_dir>/verification \
  --output-file <output_dir>/verification/gate_result.json \
  --output-json
```

Read `gate_result.json`. Key fields:

| Field                            | Meaning                                      |
|----------------------------------|----------------------------------------------|
| `rmc_exit_code`                  | 0 = parse+compile OK                         |
| `vacuity_status.is_vacuous`      | true = assertion trivially satisfied         |
| `mutation_score`                 | kill rate 0–100; must be ≥ 80                |
| `passes_gate`                    | true only when all three criteria met        |

### On failure — edit in place, retry

| Failure                      | What to fix in the files                                                |
|------------------------------|-------------------------------------------------------------------------|
| `rmc_exit_code == 5`         | Fix syntax; read `<output_dir>/verification/rmc/rmc_stderr.log`        |
| `rmc_exit_code == 4`         | Fix `.rebeca` model structure (C++ compile error)                      |
| `rmc_exit_code == 3`         | Simplify `.rebeca` (timeout — fewer statevars or actors)               |
| `is_vacuous == true`         | Strengthen assertion in `.property` — re-read Legata `Condition`/`Assure` |
| `mutation_score < 80`        | Tighten `.property` assertion against Legata assurance thresholds      |

Edit only the broken section. Do not regenerate from scratch.

### Done when `passes_gate == true`

After 3 attempts without `passes_gate`: proceed to Phase 4 with `verify_status=blocked`.

---

## Phase 4 — Score and report

Read `<output_dir>/verification/gate_result.json` and extract:
- `$rmc_exit` ← `rmc_exit_code`
- `$is_vacuous` ← `vacuity_status.is_vacuous` (false if null/missing)
- `$mutation_score` ← `mutation_score` (0 if null/missing)
- `$verify_status` ← `pass` if `passes_gate`, else `fail`|`timeout`|`blocked`

```bash
python3 <scripts>/score_single_rule.py \
  --rule-id        <rule_id> \
  --verify-status  $verify_status \
  --rmc-exit-code  $rmc_exit \
  --is-vacuous     $is_vacuous \
  --mutation-score $mutation_score \
  --assertion-id   <rule_id> \
  --output-json \
| python3 <scripts>/generate_report.py \
  --output-dir <output_dir>/reports \
  --format both
```

---

## Final output

```
=== rule_id ===
Status:     <Pass|Conditional|Fail|Blocked>
Score:      <score_total>/100
Vacuity:    <non_vacuous|vacuous|unchecked>
Mutation:   <mutation_score>%  (<killed>/<total_run> mutants)
Files:      <output_dir>/<rule_id>.rebeca
            <output_dir>/<rule_id>.property
Report:     <output_dir>/reports/summary.json
```
