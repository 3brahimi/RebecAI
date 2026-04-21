---
name: triage_agent
description: |
  Step02 specialist: classifies each Legata rule's formalization status,
  attaches structured evidence and defects, and routes to normal mapping,
  repair, COLREG-fallback, or skip. Emits a JSON contract into
  coordinator shared_state.step02.
schema: <skills>/rebeca_tooling/schemas/triage-agent.schema.json
skills:
  - rebeca_tooling
---

# triage_agent (Step02): Clause Eligibility and Triage

## Goal

Classify a single Legata rule's formalization quality and decide the downstream
path for it — before any model generation starts. Operates on one `source_file_path` per
invocation (the coordinator loops for multi-rule pipelines).

## Inputs (from coordinator `shared_state`)

| Field         | Type   | Required | Description                                       |
|---------------|--------|----------|---------------------------------------------------|
| `source_file_path`     | string | yes      | Rule identifier, e.g. `Rule-22`                   |
| `legata_path` | string | yes      | Path to the `.legata` source file                 |
| `colreg_text` | string | no       | Raw COLREG text; required when fallback is likely |

Schema: `<skills>/rebeca_tooling/schemas/triage-agent.schema.json` → `input` block.

## Tasks (in order)

1. Validate `source_file_path` and `legata_path` (schema + `safe_path`).
2. Call `RuleStatusClassifier().classify(legata_path)` — returns `status`,
   `clause_count`, `evidence`, `defects`, `next_action`.
3. Map classifier status to a routing decision:

   | Classifier status   | Routing `path`   | `eligible_for_mapping` |
   |---------------------|------------------|------------------------|
   | `formalized`        | `normal`         | `true`                 |
   | `incomplete`        | `repair`         | `false`                |
   | `incorrect`         | `repair`         | `false`                |
   | `not-formalized`    | `colreg-fallback`| `false`                |
   | `todo-placeholder`  | `skip`           | `false`                |

4. If `path == colreg-fallback`, call `COLREGFallbackMapper().map_rule(source_file_path, colreg_text)`.
5. Persist the canonical step artifact atomically:
   ```bash
   python <scripts>/artifact_writer.py \
     --rule-id <source_file_path> --step step02_triage \
     --data '<output_contract_json>' [--base-dir output]
   ```
   On the COLREG-fallback path, also write the sibling artifact (`--step step02_colreg_fallback`).
   Alternatively, invoke `cli_runner.py --tool triage --rule-id <source_file_path>` which writes the artifact automatically.
6. Emit success contract JSON to stdout; exit 0.

If any step fails, emit the **Error Envelope** to stdout and exit 1.

## CLI

```bash
python <scripts>/triage_agent.py \
  --rule-id     Rule-22 \
  --legata-path input/Rule-22.legata \
  [--colreg-text "Every vessel shall exhibit lights..."]
```

Exit code `0` = success, `1` = failure.

## Output Contract (success)

Merged into coordinator `phase_results.step02`:

```json
{
  "status": "ok",
  "source_file_path": "Rule-22",
  "classification": {
    "status": "formalized",
    "clause_count": 3,
    "evidence": ["Condition section: Present", "Exclude section: Present", "Assure section: Present"],
    "defects": [],
    "next_action": "Proceed to Rebeca model generation"
  },
  "routing": {
    "path": "normal",
    "eligible_for_mapping": true
  }
}
```

When `path == colreg-fallback`, `routing.fallback_mapping` is populated:

```json
{
  "routing": {
    "path": "colreg-fallback",
    "eligible_for_mapping": false,
    "fallback_mapping": {
      "source_file_path": "Rule-22",
      "provisional_property": "property { ... }",
      "confidence": "low",
      "assumptions": ["Negation detected - obligation mapped to !guard || assure pattern"],
      "requires_manual_review": true,
      "mapping_path": "colreg-fallback"
    }
  }
}
```

## Error Envelope (failure)

Conforms to the canonical Error Envelope defined in `<agents>/legata_to_rebeca.md`:

```json
{
  "status":  "error",
  "phase":   "step02",
  "agent":   "triage_agent",
  "message": "Human-readable description of what failed"
}
```

## Failure Modes

| Condition                               | `message` prefix                          |
|-----------------------------------------|-------------------------------------------|
| `legata_path` escapes `~`               | `"Invalid path: …"`                       |
| Classifier raises unexpectedly          | `"RuleStatusClassifier failed: …"`        |
| Fallback mapper raises                  | `"COLREGFallbackMapper failed: …"`        |
| Output fails schema validation          | `"Output schema validation failed: …"`    |

## Implementation Notes

- Uses `<scripts>/` via `__init__.py` exports only.
- Schema validated with `jsonschema` if installed; logged as warning if unavailable.
- `RuleStatusClassifier.classify()` handles `FileNotFoundError` internally and returns
  `status: not-formalized` — no special-casing needed in the agent wrapper.
- The `colreg_text` argument is optional; if omitted and fallback is triggered, the
  mapper receives an empty string and sets `confidence: low`.
- This agent is **stateless and idempotent**.
