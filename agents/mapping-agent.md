---
name: mapping-agent
version: 1.0.0
description: |
  Step04 specialist: generates canonical Legata→Rebeca transformation artifacts.
  Consumes the Step03 abstraction summary and produces a pair of files —
  a .rebeca actor model and a .property assertion file — for each rule.
user-invocable: false
implementation: agents/mapping-agent.py
schema: agents/mapping-agent.schema.json
skills:
  - rebeca-tooling
  - rebeca-handbook
---

# mapping-agent (Step04): Manual Mapping Core

## Goal

Translate the locked symbol namespace from Step03 into two concrete artifacts that
RMC can verify: a Timed Rebeca model file and a property file. Operates on one
`source_file_path` per invocation.

## Inputs (from coordinator `shared_state`)

| Field                | Type   | Required | Description                                         |
|----------------------|--------|----------|-----------------------------------------------------|
| `source_file_path`            | string | yes      | Rule identifier, e.g. `Rule-22`                     |
| `legata_path`        | string | yes      | Path to the `.legata` source file                   |
| `abstraction_summary`| object | yes      | Step03 output (`actor_map`, `variable_map`, `naming_contract`) |
| `output_dir`         | string | yes      | Directory where `.rebeca` and `.property` are written |

Schema: `agents/mapping-agent.schema.json` → `input` block.

## Tasks (in order)

1. Validate `legata_path` and `output_dir` (schema + `safe_path`).
2. Parse the Legata file for numeric thresholds in condition/assurance lines.
3. Generate the `.rebeca` model using the `actor_map` and `variable_map`.
4. Generate the `.property` file using the canonical assertion pattern.
5. Write both files to `output_dir`.
6. Validate output against schema.
7. Emit success contract; exit 0. On any failure emit Error Envelope; exit 1.

## Canonical Assertion Pattern

Per `transformation_patterns.md` and the Legata obligation semantics:

```
RuleN: !condition || exclusion || assurance;
```

Formal derivation: `condition ∧ ¬exclusion → assurance`
= `¬condition ∨ exclusion ∨ assurance`

| Variable source   | Role in assertion           | Operator |
|-------------------|-----------------------------|----------|
| `condition`       | trigger (negated)           | `!alias \|\|` |
| `exclusion`       | exemption (positive)        | `alias \|\|` |
| `assurance`       | obligation (positive, ANDed)| `(a1 && a2)` |
| `inferred`        | `define` only, not asserted | —        |

Multiple conditions are ORed as negations: `!c1 || !c2 || ...`  
Multiple assurances are ANDed: `(a1 && a2 && ...)`

## Model Template

```rebeca
reactiveclass {ClassName}(10) {
  statevars {
    {type} {name};
    ...
  }
  {ClassName}() {
    {name} = {default};   // false for boolean, 0 for int
    ...
  }
  msgsrv tick() {
  }
}
main {
  {ClassName} {instance}():();
}
```

## Property Template

```property
property {
  define {
    {alias} = ({instance}.{name} {op} {value});
    ...
  }
  Assertion {
    {RuleName}: !condition || exclusion || assurance;
  }
}
```

Threshold detection: numeric literals (`meters(N)`, `miles(N)`, plain `N`) are
extracted from the Legata section text. Operator is inferred from `>=`, `>`, `<=`,
`<`, or `==`; defaults to `> 0`.

## CLI

```bash
python agents/mapping-agent.py \
  --rule-id            Rule-22 \
  --legata-path        input/Rule-22.legata \
  --abstraction-json   '{"naming_contract":{...},"actor_map":[...],"variable_map":[...]}' \
  --output-dir         output/Rule-22/
```

Exit code `0` = success, `1` = failure.

## Output Contract (success)

Merged into coordinator `phase_results.step04`:

```json
{
  "status": "ok",
  "source_file_path": "Rule-22",
  "model_artifact": {
    "path": "/abs/output/Rule-22/Rule-22.rebeca",
    "content": "reactiveclass Vessel(10) { ... }"
  },
  "property_artifact": {
    "path": "/abs/output/Rule-22/Rule-22.property",
    "content": "property { define { ... } Assertion { Rule22: !isLightOn || lightRangeOk; } }"
  },
  "open_assumptions": [
    "Threshold for 'lightRange' defaulted to > 0 — refine manually"
  ]
}
```

## Error Envelope (failure)

```json
{
  "status":  "error",
  "phase":   "step04",
  "agent":   "mapping-agent",
  "message": "Human-readable description of what failed"
}
```

## Failure Modes

| Condition                              | `message` prefix                            |
|----------------------------------------|---------------------------------------------|
| `legata_path` / `output_dir` escapes ~ | `"Invalid path: …"`                         |
| `abstraction_summary` missing fields   | `"Invalid abstraction_summary: …"`          |
| No assertion terms could be built      | `"Cannot build assertion: no condition …"`  |
| File write failure                     | `"Failed to write artifact: …"`             |
| Output schema violation                | `"Output schema validation failed: …"`      |

## Implementation Notes

- No new tooling scripts: uses `safe_path` from `utils.py` only.
- Numeric threshold extraction is a pure-regex pass over the Legata condition text;
  does not invoke RMC.
- All generated Rebeca identifiers come directly from the Step03 `variable_map` —
  no new symbols are invented.
- Forbidden operators (`->`, `=>`) are never emitted; `||` and `&&` only.
- This agent is **idempotent**: re-running with the same inputs overwrites files in place.
