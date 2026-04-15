---
name: verification_agent
version: 1.0.0
description: |
  Step06 specialist for RMC verification, vacuity checking, and mutation scoring.
  Orchestrates run_rmc → vacuity_checker → mutation_engine for a single rule.
user-invocable: false
schema: skills/rebeca_tooling/schemas/verification-agent.schema.json
skills:
  - rebeca_tooling
  - rebeca_handbook
---

# Step06 Subagent: Verification and Mutation Scoring

## Goal

Validate generated artifacts with RMC, check vacuity of passing properties,
and compute a mutation score. Return a fully machine-actionable outcome.

## Input Schema

| Field           | Type    | Required | Description                                |
|-----------------|---------|----------|--------------------------------------------|
| `source_file_path`       | string  | yes      | Rule identifier (e.g. `Rule-22`)           |
| `model_path`    | string  | yes      | Path to `.rebeca` model file               |
| `property_path` | string  | yes      | Path to `.property` file                   |
| `jar_path`      | string  | yes      | Path to `rmc.jar`                          |
| `output_dir`    | string  | yes      | Directory to write RMC artefacts into      |
| `timeout`       | integer | no       | Per-invocation timeout in seconds (≥1, default 120) |

## Pipeline

```
run_rmc(model, property, jar, output_dir, timeout)
    │
    ├─ exit_code != 0 ──► emit contract with verified=false, skip vacuity + mutation
    │
    └─ exit_code == 0
           │
           ├─► check_vacuity(jar, model, property, output_dir, timeout)
           │       └─► vacuity_status object
           │
           └─► MutationEngine (all 8 strategies)
                   │   For each mutation: run_rmc → killed if exit_code != 0
                   └─► mutation_score = killed / total * 100.0
```

## RMC Exit Code Classification

| Exit Code | `rmc_outcome`        | `verified` |
|-----------|----------------------|------------|
| 0         | `verified`           | `true`     |
| 1         | `invalid_inputs`     | `false`    |
| 3         | `timeout`            | `false`    |
| 4         | `cpp_compile_failed` | `false`    |
| 5         | `parse_failed`       | `false`    |
| other     | `unknown`            | `false`    |

## Mutation Strategies

**Model-side** (applied to `.rebeca` content):
- `transition_bypass`
- `predicate_flip`
- `assignment_mutation`

**Property-side** (applied to `.property` content):
- `comparison_value_mutation`
- `boolean_predicate_negation`
- `assertion_negation`
- `assertion_predicate_inversion`
- `logical_swap`
- `variable_swap`

A mutant is **killed** if its `run_rmc` exit code is non-zero.

## Output Contract (success)

```json
{
  "status": "ok",
  "source_file_path": "Rule-22",
  "verified": true,
  "rmc_exit_code": 0,
  "rmc_outcome": "verified",
  "rmc_output_dir": "/path/to/output",
  "vacuity_status": {
    "is_vacuous": false,
    "precondition_used": "!vessel_hasTarget",
    "secondary_exit_code": 4,
    "secondary_output_dir": "/path/to/secondary",
    "explanation": "NON-VACUOUS: negated property fails to compile — property exercises its precondition."
  },
  "mutation_score": 45.5,
  "mutation_detail": { "total": 11, "killed": 5, "survived": 6 },
  "open_assumptions": [
    "NOTE: run_rmc only compiles the model — mutation_score reflects syntactic kills only, not semantic/runtime kills."
  ]
}
```

## Error Envelope

```json
{
  "status":  "error",
  "phase":   "step06",
  "agent":   "verification_agent",
  "message": "Human-readable description of failure"
}
```

Emit on: invalid paths, `run_rmc` internal exception, `check_vacuity` exception,
`MutationEngine` instantiation failure.

**Do not** emit an error envelope for non-zero `rmc_exit_code` — that is a valid
`verified=false` outcome, not an agent failure.

## Output Patch (for coordinator)

- `workflow_summary.step06`
- `verification_report` (entire output contract)
- `single_rule_scorecard.failure_reasons` ← `rmc_outcome` when `verified=false`
- `single_rule_scorecard.remediation_hints` ← populated from `vacuity_status.explanation`
  and survived mutation list
