---
name: synthesis_agent
description: |
  Step05 specialist for LLM-assisted candidate property generation.
  Runs in parallel with Step04 (mapping_agent) after Step03 completes.
  ALL outputs are tagged is_candidate=true, mapping_path=synthesis-agent, and
  MUST be routed to Step06 (verification_exec) before any downstream use.
schema: <skills>/rebeca_tooling/schemas/synthesis-agent.schema.json
skills:
  - rebeca_tooling
  - rebeca_handbook
---

# Step05 Subagent: LLM-Assisted Candidate Generation

## Goal

Generate alternative candidate Rebeca model+property pairs from the same
Step03 abstraction summary that feeds Step04. Candidates explore formulations
that the deterministic mapping_agent cannot produce. Every artifact is
explicitly non-final and must pass Step06 verification before promotion.

## Position in Pipeline

```
Step03 (abstraction_agent)
         │
         ├──► Step04 (mapping_agent)     [deterministic, final path]
         │
         └──► Step05 (synthesis_agent)    [candidate path ← THIS AGENT]
                        │
                        └──► Step06 (verification_exec)   [MANDATORY]
```

## Input Schema

| Field                | Type            | Required | Description                              |
|----------------------|-----------------|----------|------------------------------------------|
| `source_file_path`            | string          | yes      | Rule identifier (e.g. `Rule-22`)         |
| `abstraction_summary`| object          | yes      | Step03 output: `actor_map`, `variable_map` |
| `legata_text`        | string          | no       | Raw Legata source (enriches heuristics)  |
| `output_dir`         | string          | yes      | Directory to write candidate artifacts   |

## Generation Strategies

Two candidate formulations are generated from a single invocation:

### Strategy 1: `base`
Identical assertion logic to Step04 (`!condition || exclusion || assurance`)
but with an alternative variable binding — each actor gets its own
`reactiveclass` queue size derived from the number of statevars it owns.
Confidence: **high** when `variable_map` is non-empty; **medium** otherwise.

### Strategy 2: `temporal`
Wraps the base assertion in a `LTL` block with a `G(assertion)` temporal
formula, enabling model checkers that support LTL properties. Uses the same
`define` block as the base strategy.
Confidence: **medium** always (temporal wrapping introduces additional
  assumptions about the Kripke structure).

## Candidate Artifact Tagging

Every entry in `candidate_artifacts` carries:

| Field          | Value       | Meaning                                      |
|----------------|-------------|----------------------------------------------|
| `mapping_path` | `"synthesis-agent"`| Distinguishes from Step04 (`"legata"`) and Step02 COLREG fallback |
| `is_candidate` | `true`      | Coordinator MUST route to Step05 before use   |

The coordinator checks `is_candidate == true` before committing any artifact
to `generated_files` — this is the mandatory verification gate.

## Output Contract (success)

```json
{
  "status": "ok",
  "source_file_path": "Rule-22",
  "candidate_artifacts": [
    {
      "artifact_id":      "Rule-22_synth_base",
      "strategy":         "base",
      "model_path":       "/path/Rule-22_synth_base.rebeca",
      "property_path":    "/path/Rule-22_synth_base.property",
      "model_content":    "reactiveclass ...",
      "property_content": "property { ... }",
      "mapping_path":     "synthesis-agent",
      "is_candidate":     true,
      "confidence":       "high",
      "assumptions":      []
    },
    {
      "artifact_id":      "Rule-22_synth_temporal",
      "strategy":         "temporal",
      "model_path":       "/path/Rule-22_synth_temporal.rebeca",
      "property_path":    "/path/Rule-22_synth_temporal.property",
      "model_content":    "reactiveclass ...",
      "property_content": "property { define {...} Assertion {...} LTL { G(Rule22); } }",
      "mapping_path":     "synthesis-agent",
      "is_candidate":     true,
      "confidence":       "medium",
      "assumptions":      ["LTL block requires Timed Rebeca LTL model checker support"]
    }
  ],
  "open_assumptions": []
}
```

## Error Envelope

```json
{
  "status":  "error",
  "phase":   "step05",
  "agent":   "synthesis_agent",
  "message": "Human-readable description of failure"
}
```

Emit on: invalid/escaped paths, empty abstraction_summary, artifact write
failure, schema validation violation.

## Canonical Artifact Persistence (REQUIRED)

After all candidate artifacts are written and the output contract is assembled, persist the canonical step artifact atomically **before** returning output to the coordinator:

```bash
python <scripts>/artifact_writer.py \
  --rule-id <source_file_path> --step step05_candidates \
  --data '<output_contract_json>' [--base-dir output]
```

The `step05_candidates.json` artifact is required by Gate 0 and must contain `candidate_artifacts[]` with `model_path`, `property_path`, `is_candidate`, `confidence`, `mapping_path` per item.

## Output Patch (for coordinator)

- `workflow_summary.step05`
- `phase_results.step05` ← full output contract
- `candidate_artifacts[]` ← each entry appended to coordinator's transformed_artifacts
  with `is_candidate: true` for mandatory Step05 routing
