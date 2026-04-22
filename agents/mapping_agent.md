---
name: mapping_agent
description: |
  Step04 specialist: generates canonical Legata→Rebeca transformation artifacts.
  Consumes the Step03 abstraction summary and produces a pair of files —
  a .rebeca actor model and a .property assertion file — for each rule.
schema: <skills>/rebeca_tooling/schemas/mapping-agent.schema.json
skills:
  - rebeca_tooling
  - rebeca_handbook
---

# mapping_agent (Step04): Refine Existing Model and Property

## Goal

Refine the existing `.rebeca` model and `.property` file (copied from reference files in Step01) to align with the Legata semantics. Uses the locked symbol namespace from Step03 to ensure consistency. Operates on files already present in `output_dir`.

## Inputs (from coordinator `shared_state`)

| Field                | Type   | Required | Description                                         |
|----------------------|--------|----------|-----------------------------------------------------|
| `rule_id`            | string | yes      | Rule identifier, e.g. `Rule-22`                     |
| `legata_input`        | string | yes      | Path to the `.legata` source file                   |
| `abstraction_summary`| object | yes      | Step03 output (`actor_map`, `variable_map`, `naming_contract`) |
| `output_dir`         | string | yes      | Directory containing existing `.rebeca` and `.property` files |

**Critical:** The files `<output_dir>/<rule_id>.rebeca` and `<output_dir>/<rule_id>.property` MUST already exist (copied from reference files in Step01). This agent refines them in place.

Schema: `<skills>/rebeca_tooling/schemas/mapping-agent.schema.json` → `input` block.

## Tasks (in order)

1. **Read existing files**: Load `<output_dir>/<rule_id>.rebeca` and `<output_dir>/<rule_id>.property` (these were copied from reference files in Step01).
2. Validate `<legata_input>` and `<output_dir>` (schema + `safe_path`).
3. Parse the Legata file for numeric thresholds in condition/assurance lines.
4. **Refine the `.rebeca` model** using the `actor_map` and `variable_map` from Step03, preserving structure where possible.
5. **Refine the `.property` file** using the canonical assertion pattern, updating the `define` block and `Assertion` to match Legata semantics.
6. Write both refined files back to `<output_dir>` (overwrite in place).
7. Validate output against schema.
8. Return the output contract JSON to the coordinator (do not call artifact_writer - coordinator handles persistence).
9. On any failure emit Error Envelope.

## Canonical Assertion Pattern

Per the Legata obligation semantics (see `legata_to_rebeca` skill):

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

## Output Contract (success)

Merged into coordinator `phase_results.step04`:

```json
{
  "status": "ok",
  "rule_id": "Rule-22",
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
  "agent":   "mapping_agent",
  "message": "Human-readable description of what failed"
}
```

## Failure Modes

| Condition                              | `message` prefix                            |
|----------------------------------------|---------------------------------------------|
| `<legata_input>` / `<output_dir>` escapes ~ | `"Invalid path: …"`                         |
| `<abstraction_summary>` missing fields   | `"Invalid abstraction_summary: …"`          |
| No assertion terms could be built      | `"Cannot build assertion: no condition …"`  |
| File write failure                     | `"Failed to write artifact: …"`             |
| Output schema violation                | `"Output schema validation failed: …"`      |

## Implementation Notes

- No new tooling scripts: uses `safe_path` from `utils.py` only.
- **Refinement strategy**: Read existing files first, then update specific sections (statevars, define block, assertion) while preserving overall structure.
- Numeric threshold extraction is a pure-regex pass over the Legata condition text;
  does not invoke RMC.
- All generated Rebeca identifiers come directly from the Step03 `variable_map` —
  no new symbols are invented.
- Forbidden operators (`->`, `=>`) are never emitted; `||` and `&&` only.
- This agent is **idempotent**: re-running with the same inputs overwrites files in place.
