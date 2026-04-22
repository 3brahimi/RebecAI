---
name: abstraction_agent
description: |
  Step03 specialist: produces stable abstraction rules before model/property
  generation. Extracts actors and conditions from Legata, applies deterministic
  naming conventions, discretizes to Rebeca-compatible types, and emits a
  JSON contract into coordinator shared_state.step03.
schema: <skills>/rebeca_tooling/schemas/abstraction-agent.schema.json
skills:
  - rebeca_tooling
  - rebeca_handbook
---

# abstraction_agent (Step03): Abstraction and Discretization Setup

## Goal

Lock in a deterministic symbol namespace before any model or property file is
generated, preventing symbol collisions and hallucinated identifiers in later phases.
Operates on one `source_file_path` per invocation.

## Inputs (from coordinator `shared_state`)

| Field                | Type   | Required | Description                                         |
|----------------------|--------|----------|-----------------------------------------------------|
| `rule_id`            | string | yes      | Rule identifier, e.g. `Rule-22`                     |
| `legata_input`        | string | yes      | Path to the `.legata` source file                   |
| `output_dir`         | string | yes      | Directory containing reference `.rebeca` and `.property` files |
| `snapshot_path`      | string | no       | Step01 snapshot JSON; seeds variable_map when present     |
| `colreg_text`        | string | no       | Supplementary COLREG text for actor/condition extraction |

**Note:** The reference files `<output_dir>/<rule_id>.rebeca` and `<output_dir>/<rule_id>.property` (copied in Step01) should be read to extract existing symbols and structure. This ensures the abstraction aligns with what's already present.

Schema: `<skills>/rebeca_tooling/schemas/abstraction-agent.schema.json` → `input` block.

## Tasks (in order)

1. Validate `<legata_input>` and `<output_dir>` (schema + `safe_path`).
2. **Read existing reference files**: Load `<output_dir>/<rule_id>.rebeca` and `<output_dir>/<rule_id>.property` to extract existing actors, statevars, and property definitions.
3. Read Legata content; extract actors and section-labelled conditions.
4. Supplement with existing symbols from reference files (Step 2).
5. Supplement with `<snapshot_path>` state variables (when provided).
6. Supplement with `<colreg_text>` keyword corpus (when provided).
7. Apply naming conventions deterministically (see table below).
8. Map each concept to a Rebeca type and bounds.
9. Validate output against schema.
10. Persist the canonical step artifact atomically:
   ```bash
   python <scripts>/artifact_writer.py \
     --rule-id <rule_id> --step step03_abstraction \
     --data '<output_contract_json>' [--base-dir output]
   ```
11. Emit success contract; exit 0. On any failure emit Error Envelope; exit 1.

## Naming Contract (fixed — never changes between runs)

| Symbol kind         | Style         | Example                         |
|---------------------|---------------|---------------------------------|
| `reactiveclass`     | PascalCase    | `Ship`, `Vessel`, `Aircraft`    |
| `statevars`         | camelCase     | `hasLight`, `lightRange`        |
| Instance in `main`  | lowerCamelCase| `ship`, `vessel1`               |
| Property `define`   | camelCase     | `isMoving`, `lightOn`           |
| `Assertion` name    | PascalCase    | `Rule22`, `SafetyCheck`         |

## Discretization Rules

| Legata concept pattern                  | Rebeca type | Bounds hint        |
|-----------------------------------------|-------------|--------------------|
| `is…`, `has…`, `can…`, presence verb    | `boolean`   | —                  |
| speed, range, distance, count           | `int`       | `[0, 30]` default  |
| binary on/off, exhibit/hide             | `boolean`   | —                  |
| Ambiguous (fallback)                    | `boolean`   | —                  |

## Output Contract (success)

Merged into coordinator `phase_results.step03`:

```json
{
  "status": "ok",
  "rule_id": "Rule-22",
  "abstraction_summary": {
    "naming_contract": {
      "reactive_class_style": "PascalCase",
      "state_var_style": "camelCase",
      "instance_style": "lowerCamelCase",
      "define_alias_style": "camelCase",
      "assertion_name_style": "PascalCase"
    },
    "actor_map": [
      { "legata_actor": "vessel", "rebeca_class": "Vessel", "rebeca_instance": "vessel" }
    ],
    "variable_map": [
      {
        "legata_concept": "vessel exhibits lights",
        "rebeca_name": "hasLight",
        "rebeca_type": "boolean",
        "define_alias": "isLightOn",
        "source": "condition"
      },
      {
        "legata_concept": "light range",
        "rebeca_name": "lightRange",
        "rebeca_type": "int",
        "bounds": { "min": 0, "max": 30 },
        "define_alias": "lightRangeOk",
        "source": "assurance"
      }
    ]
  },
  "open_assumptions": [
    "Default integer bounds [0, 30] applied to 'lightRange' — refine manually"
  ]
}
```

## Error Envelope (failure)

```json
{
  "status":  "error",
  "phase":   "step03",
  "agent":   "abstraction_agent",
  "message": "Human-readable description of what failed"
}
```

## Failure Modes

| Condition                            | `message` prefix                          |
|--------------------------------------|-------------------------------------------|
| `<legata_input>` escapes `~`          | `"Invalid path: …"`                       |
| Legata file unreadable               | `"Failed to read legata file: …"`         |
| Snapshot JSON malformed              | `"Invalid snapshot JSON: …"`              |
| Empty abstraction (no actors/vars)   | `"Abstraction produced no symbols: …"`    |
| Output schema violation              | `"Output schema validation failed: …"`    |

## Implementation Notes

- No new tooling scripts introduced: uses `extract_state_variables` and
  `extract_property_identifiers` from `snapshotter.py` (via `__init__.py`).
- Naming conversion is pure string transformation — fully deterministic.
- `snapshot_path` seeds additional state variables discovered by Step01
  (prevents the abstraction from diverging from the already-snapshotted baseline).
- This agent is **stateless and idempotent**.
