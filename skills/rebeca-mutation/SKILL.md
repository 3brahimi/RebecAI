---
name: rebeca-mutation
version: 1.1.0
description: |
  Orchestrates the full Mutation Testing suite for Rebeca formal verification.
  Generates controlled mutations of .rebeca model files and .property files,
  runs RMC on each mutant, and computes a Mutation Score. Integrates vacuity checking.
trigger_phrases:
  - "mutation testing"
  - "run mutation suite"
  - "run mutation testing"
  - "mutate rebeca model"
  - "generate mutations"
  - "mutate property"
  - "check vacuity"
  - "mutation score"
capabilities:
  - mutation_suite_execution
  - vacuity_checking
  - mutation_score_computation
  - mutation_report_generation
---

# rebeca-mutation
...

## When to invoke

| Trigger | Action |
|---------|--------|
| After `run_rmc` returns exit code 0 (property verified) | Run vacuity check first; then run mutation suite |
| During WF-06 (Verification) quality gate | Compute mutation score; fail if score < threshold |
| On-demand quality audit of an existing `.property` file | Run targeted mutation strategies |

---

## Mutation Strategies

Eight strategies are implemented in
`~/.agents/skills/rebeca-tooling/scripts/mutation_engine.py`:

| ID | Target | What changes | Expected outcome |
|----|--------|-------------|-----------------|
| `transition_bypass` | `.rebeca` | Comments out a state-variable assignment inside `msgsrv` | Mutant should be **killed** (property detects missing transition) |
| `predicate_flip` | `.rebeca` | Negates an `if`-condition (`if (x)` → `if (!x)`) | Mutant should be **killed** |
| `assignment_mutation` | `.rebeca` | Increments a numeric literal by 1 (`= N` → `= N+1`) | Mutant should be **killed** |
| `comparison_value_mutation` | `.property` | Increments comparison constant in `define` block | Mutant should be **killed** |
| `boolean_predicate_negation` | `.property` | Negates a boolean term in an assertion (`x` → `!x`) | Mutant should be **killed** |
| `assertion_negation` | `.property` | Negates the full assertion expression | Mutant should be **killed** (RMC finds counterexample) |
| `assertion_predicate_inversion` | `.property` | Swaps implication sides (`A → B` → `B → A`) | Mutant should be **killed** |
| `logical_swap` | `.property` | Swaps `&&` ↔ `\|\|` in the assertion | Mutant should be **killed** |

---

## Mutation Score Formula

```
Mutation Score = (Killed Mutants) / (Total Mutants) × 100
```

- **Killed**: RMC returns non-zero exit code on the mutant (counterexample found or error).
- **Survived**: RMC returns exit code 0 on the mutant — the property failed to detect the error.
- **Equivalent**: Mutant produces semantically identical behaviour (manual review required; flag for human).

Target threshold: **≥ 80%** to pass the WF-06 quality gate.

---

## Output JSON Schema

The skill emits a JSON report compatible with the agent's scoring pipeline:

```json
{
  "rule_id": "COLREG-Rule22",
  "mutation_score": 87.5,
  "total_mutants": 16,
  "killed": 14,
  "survived": 2,
  "errors": 0,
  "vacuity": {
    "is_vacuous": false,
    "precondition_used": "!hasLight || (lightRange >= 6)",
    "explanation": "NON-VACUOUS: A counterexample exists for !Precondition; the property is meaningful."
  },
  "per_strategy": [
    {
      "strategy": "transition_bypass",
      "total": 3,
      "killed": 3,
      "survived": 0
    },
    {
      "strategy": "assertion_negation",
      "total": 1,
      "killed": 1,
      "survived": 0
    }
  ],
  "survived_mutations": [
    {
      "mutation_id": "logical_swap_0",
      "strategy": "logical_swap",
      "description": "Swapped && -> || at offset 142 in assertion",
      "artifact": "property"
    }
  ]
}
```

---

## Python Workflow

```python
from scripts import MutationEngine, Mutation, check_vacuity, run_rmc
from pathlib import Path
import json, os, tempfile

JAR    = "~/.agents/skills/rebeca-tooling/bin/rmc.jar"
MODEL  = "models/rule22.rebeca"
PROP   = "models/rule22.property"
OUTDIR = "output/rule22"

# Step 1 — Vacuity check (only run if RMC already passed)
vacuity = check_vacuity(jar=JAR, model=MODEL, property_file=PROP, output_dir=OUTDIR)
if vacuity["is_vacuous"]:
    print("VACUOUS — fix the property before running mutation suite")
    raise SystemExit(2)

# Step 2 — Generate all mutants
engine = MutationEngine(rule_id="Rule22", model_content=Path(MODEL).read_text(),
                        property_content=Path(PROP).read_text())
mutants: list[Mutation] = engine.generate_all()

# Step 3 — Run RMC on each mutant, collect results
killed = 0
survived_list = []
per_strategy: dict[str, dict] = {}

for mut in mutants:
    strat = mut.strategy
    per_strategy.setdefault(strat, {"total": 0, "killed": 0, "survived": 0})
    per_strategy[strat]["total"] += 1

    suffix = ".rebeca" if mut.artifact == "model" else ".property"
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix,
                                    delete=False, encoding="utf-8") as tmp:
        tmp.write(mut.mutated_content)
        tmp_path = tmp.name

    try:
        mut_model = tmp_path if mut.artifact == "model" else MODEL
        mut_prop  = tmp_path if mut.artifact == "property" else PROP
        exit_code = run_rmc(jar=JAR, model=mut_model, property_file=mut_prop,
                            output_dir=f"{OUTDIR}_mut_{mut.mutation_id}",
                            timeout_seconds=60)
    finally:
        os.unlink(tmp_path)

    if exit_code != 0:
        killed += 1
        per_strategy[strat]["killed"] += 1
    else:
        per_strategy[strat]["survived"] += 1
        survived_list.append({"mutation_id": mut.mutation_id,
                               "strategy": strat,
                               "description": mut.description,
                               "artifact": mut.artifact})

total = len(mutants)
score = (killed / total * 100) if total else 0.0

report = {
    "rule_id": "Rule22",
    "mutation_score": round(score, 1),
    "total_mutants": total,
    "killed": killed,
    "survived": total - killed,
    "errors": 0,
    "vacuity": vacuity,
    "per_strategy": [{"strategy": s, **v} for s, v in per_strategy.items()],
    "survived_mutations": survived_list,
}
print(json.dumps(report, indent=2))
```

---

## CLI Usage

Run the vacuity checker standalone:

```bash
python3 ~/.agents/skills/rebeca-tooling/scripts/vacuity_checker.py \
  --jar      ~/.agents/skills/rebeca-tooling/bin/rmc.jar \
  --model    models/rule22.rebeca \
  --property models/rule22.property \
  --output-dir output/rule22 \
  --output-json
```

Generate mutations and print JSON (no RMC run — dry-run):

```bash
python3 ~/.agents/skills/rebeca-tooling/scripts/mutation_engine.py \
  --rule-id   Rule22 \
  --model     models/rule22.rebeca \
  --property  models/rule22.property \
  --strategy  all \
  --output-json
```

Run single strategy only:

```bash
python3 ~/.agents/skills/rebeca-tooling/scripts/mutation_engine.py \
  --rule-id   Rule22 \
  --model     models/rule22.rebeca \
  --property  models/rule22.property \
  --strategy  transition_bypass \
  --output-json
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Mutation suite ran; JSON report on stdout |
| 1 | Invalid inputs (missing files, bad arguments) |
| 2 | Vacuity check aborted the run (property is vacuous) |

---

## WF-06 Integration

During **WF-06 (Verification)**, after `run_rmc` exits 0, invoke this skill as a
quality gate:

```python
# Inside WF-06 handler
if rmc_exit_code == 0:
    report = run_mutation_suite(jar, model, property_file, output_dir)
    if report["vacuity"]["is_vacuous"]:
        wf_status = "VACUOUS"     # property needs rework
    elif report["mutation_score"] < 80:
        wf_status = "WEAK"        # property passes but misses mutations
    else:
        wf_status = "VERIFIED"    # strong verification
```

The `wf_status` feeds into the 100-point rubric score:
- `VACUOUS`  → `verification_outcome` = 0 pts
- `WEAK`     → `verification_outcome` = partial (proportional to mutation score)
- `VERIFIED` → `verification_outcome` = full 25 pts

---

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Property has no `define` block | `comparison_value_mutation` generates 0 mutants | Expected — not an error; other strategies still run |
| All mutants survive | Mutation score = 0% | Property likely vacuous or too weak; rewrite assertion |
| Vacuity check times out (exit 3) | `is_vacuous = None` | Increase `--timeout-seconds`; model may be too large for secondary pass |
| Mutant compile error (exit 4) | Counted as "killed" in default mode | Correct — a mutation that breaks compilation still kills the mutant |
| `variable_swap` finds no pairs | Generates 0 mutants | Model has only one actor variable per namespace; not an error |
| Double-negation in negated property | `!!x` in vacuity file | `build_negated_property` simplifies this automatically |
