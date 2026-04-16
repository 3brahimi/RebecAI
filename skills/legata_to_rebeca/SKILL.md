---
name: legata-to-rebeca
description: Step-by-step operational guidance for transforming Legata clauses into verified Rebeca models — covers all eight steps including RMC execution, scoring, and reporting.
---

# Legata → Rebeca Transformation Workflow

## When to Use
Use this skill when transforming a COLREG maritime safety rule from Legata formal specification into a verifiable Rebeca actor model.

---

## Script Path Resolution

All dumb tools live in the `rebeca_tooling` skill. Resolve their location before any step:

```bash
# When running inside .github/ context:
SCRIPTS=".github/skills/rebeca_tooling/scripts"

# When running inside .claude/ or ~/.agents/ context:
# SCRIPTS="$HOME/.agents/skills/rebeca_tooling/scripts"
```

Resolve the RMC jar path:

```bash
# Option 1: read the pinned path written by setup.py
JAR=$(cat .github/skills/rmc_path.txt 2>/dev/null)

# Option 2: let pre_run_rmc_check.py auto-provision it
python3 $SCRIPTS/pre_run_rmc_check.py
JAR=$(cat .github/skills/rmc_path.txt)

# Option 3: common fallback locations
# .github/rmc/rmc.jar  |  ~/.agents/rmc/rmc.jar  |  ~/.claude/rmc/rmc.jar
```

---

## Step01 — Toolchain and Inputs Initialization

Validate prerequisites and provision RMC before doing anything else.

```bash
python3 $SCRIPTS/pre_run_rmc_check.py
python3 $SCRIPTS/verify_installation.py --rmc-jar $JAR
```

**Fail fast if:**
- `rmc.jar` not found or invalid
- Source Legata file does not exist
- Reference `.rebeca` or `.property` file does not exist

**Capture golden snapshot:**
```bash
python3 $SCRIPTS/snapshotter.py \
  --model path/to/SimulationModelCode.rebeca \
  --property path/to/SimulationModelCode.property \
  --output output/snapshots/Rule22.snapshot.json \
  --output-json
```

---

## Step02 — Clause Eligibility and Triage

Classify the Legata rule before attempting transformation.

```bash
python3 $SCRIPTS/classify_rule_status.py \
  --legata-path legata/colreg/Rule22.txt \
  --output-json
```

**Routing decisions based on `classification.status`:**

| `status` | `routing.path` | Next action |
|----------|---------------|-------------|
| `formalized` | `normal` | Proceed to Step03 |
| `not-formalized` | `colreg-fallback` | Run fallback mapper, then Step03 |
| `incomplete` or `incorrect` | `repair` | Surface defects, block |
| `todo-placeholder` | `skip` | Emit skip summary, stop |

For `colreg-fallback` path:
```bash
python3 $SCRIPTS/colreg_fallback_mapper.py \
  --colreg-text legata/colreg/Rule22.txt \
  --rule-id Rule-22 \
  --output-json
```

---

## Step03 — Abstraction and Discretization

Extract actors and variables from the Legata source. No script — reason from source text.

**Naming conventions (mandatory):**
- Actor classes: `PascalCase` (e.g., `OwnShip`, `TargetVessel`)
- State variables: `camelCase` (e.g., `shipLength`, `mastheadLightRange`)
- Boolean guards: prefix `is` or `has` (e.g., `isLongerThan50m`, `hasMastheadLight`)
- Legata `meters(N)` → integer `N` in Rebeca

**Output:** `actor_map` and `variable_map` — at least one actor and one variable required.

---

## Step04 — Manual Mapping (generate `.rebeca` and `.property`)

### Property file structure

```
property {
  define {
    // Boolean variables for guards and assertions
    ship1_longer_50m = (s1.ship_length > 50);
    ship1_lights_ok  = (s1.masthead_light_range >= 6 && s1.side_light_range >= 3);
  }
  Assertion {
    // Pattern: !guard || exclusion || assurance
    Rule22a: !ship1_longer_50m || ship1_lights_ok;
  }
}
```

### Allowed operators
`<` `>` `==` `<=` `>=` `&&` `||` `!` `^`

### Forbidden patterns
- Implication: `->` `=>`
- Temporal operators in `Assertion` section
- Undefined variable references
- Chained assignments: `x = (y = value)`

### Assertion template
```
RuleXX: !conditionVariable || !excludeVariable || assureVariable;
```

---

## Step05 — LLM-Assisted Candidate Generation (parallel with Step04)

Generate property mutation candidates for semantic strength testing.

```bash
python3 $SCRIPTS/mutation_engine.py \
  --rule-id Rule-22 \
  --model output/Rule-22.rebeca \
  --property output/Rule-22.property \
  --run-with-jar $JAR \
  --run-with-model output/Rule-22.rebeca \
  --run-with-property output/Rule-22.property \
  --run-timeout 60 \
  --max-mutants 50 \
  --total-timeout 600 \
  --seed 42 \
  --output-json
```

**All Step05 outputs are candidates** (`is_candidate=true`). They MUST be validated by Step06 before any downstream use.

---

## Step06 — RMC Verification + Vacuity + Mutation Scoring

This step is **mandatory**. Do not skip it or mark it complete without actually running the scripts.

### 6a — Run RMC model checker

```bash
python3 $SCRIPTS/run_rmc.py \
  --jar $JAR \
  --model output/Rule-22.rebeca \
  --property output/Rule-22.property \
  --output-dir output/verification \
  --timeout-seconds 120
```

**Exit code interpretation:**

| Exit code | Meaning | Action |
|-----------|---------|--------|
| `0` | Property verified — no counterexample | Proceed to 6b |
| `3` | Timeout | Report `rmc_outcome: timeout`; block with explanation |
| `4` | C++ compile failed | Report `rmc_outcome: cpp_compile_failed`; route back to Step04 |
| `5` | Parse failed — syntax error in `.rebeca` or `.property` | Report `rmc_outcome: parse_failed`; route back to Step04 |

### 6b — Vacuity check (only if Step06a exit code == 0)

```bash
python3 $SCRIPTS/vacuity_checker.py \
  --jar $JAR \
  --model output/Rule-22.rebeca \
  --property output/Rule-22.property \
  --output-dir output/verification \
  --timeout-seconds 60 \
  --output-json
```

If `is_vacuous == true`, the property passes trivially. Route back to Step05 for a stronger candidate.

### 6c — Mutation scoring (only if Step06a exit code == 0)

```bash
python3 $SCRIPTS/mutation_engine.py \
  --rule-id Rule-22 \
  --model output/Rule-22.rebeca \
  --property output/Rule-22.property \
  --strategy all \
  --output-json
```

`mutation_score` must be `>= 80.0` to proceed. If below threshold, route back to Step05.

---

## Step07 — Packaging

Copy verified artifacts to the destination directory.

```bash
mkdir -p output/packaged/Rule-22/{model,property,logs}
cp output/Rule-22.rebeca          output/packaged/Rule-22/model/
cp output/Rule-22.property        output/packaged/Rule-22/property/
cp output/verification/*.log      output/packaged/Rule-22/logs/
```

---

## Step08 — Scoring and Reporting

This step is **mandatory**. Do not skip it or summarize without running the scripts.

### 8a — Score the rule

```bash
python3 $SCRIPTS/score_single_rule.py \
  --rule-id Rule-22 \
  --model output/packaged/Rule-22/model/Rule-22.rebeca \
  --property output/packaged/Rule-22/property/Rule-22.property \
  --verify-status pass \
  --output-json > output/scorecard_Rule-22.json
```

**Scoring rubric (100 points):**

| Dimension | Points | Basis |
|-----------|--------|-------|
| Syntax correctness | 10 | RMC exit code 0 |
| Semantic alignment | 55 | `mutation_score × 0.50` + vacuity pass bonus (5 pts) |
| Verification outcome | 25 | RMC verified with no counterexample |
| Hallucination penalty | −10 | Fabricated actors/variables/rule references |

### 8b — Generate aggregate report

```bash
python3 $SCRIPTS/generate_report.py \
  < output/scorecard_Rule-22.json \
  > output/report.json
```

**Required output files:**
- `output/report.json` — machine-readable aggregate report
- `output/report.md` — human-readable Markdown summary

---

## Transformation Examples

### Equipment Range (Rule 22)

```
Legata condition: OS.Length > meters(50)

Rebeca define:  ship1_longer_50m = (s1.ship_length > 50);
                ship1_lights_ok  = (s1.masthead_light_range >= 6 && s1.side_light_range >= 3);
Assertion:      Rule22a: !ship1_longer_50m || ship1_lights_ok;
```

### Exclude Blocks (Rule 23)

```
Legata exclude: OS.Length < meters(12)

Rebeca define:  isSmall       = (s1.ship_length < 12);
                isPowerDriven = (s1.vessel_type == 0);
                lightsOn      = (s1.masthead_light_on && s1.side_lights_on);
Assertion:      Rule23: !isPowerDriven || isSmall || lightsOn;
```

---

## Non-Negotiable Rules

1. **Never skip Step06** — do not declare the transformation complete without running `run_rmc.py`
2. **Never skip Step08** — do not summarize without running `score_single_rule.py` and `generate_report.py`
3. **Step05 outputs are always candidates** — always route them through Step06 before packaging
4. **No silent skips** — if a step fails, surface the error; do not silently continue
5. **Fail fast on missing inputs** — validate all three inputs in Step01 before any transformation work
