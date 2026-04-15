---
name: reporting-agent
version: 1.0.0
description: |
  Step08 specialist for aggregate scoring and report generation.
  Wraps ReportGenerator (generate_report.py) to produce report.json
  and report.md from coordinator-supplied per-rule scorecards.
user-invocable: false
skills:
  - rebeca-tooling
  - rebeca-handbook
---

# Step08 Subagent: Scoring and Reporting

## Goal

Consume per-rule scorecards assembled by the coordinator (from Step05 outputs),
finalize aggregate metrics via `ReportGenerator`, and write `report.json` +
`report.md` to the designated output directory.

## Scorecard Contract

Each scorecard passed to this agent MUST conform to the fields consumed by
`ReportGenerator.add_scorecard()`:

| Field               | Type           | Source               |
|---------------------|----------------|----------------------|
| `source_file_path`           | string         | Step01 input          |
| `score_total`       | int (0–100)    | `RubricScorer`       |
| `status`            | Pass/Fail/Blocked/Conditional/Unknown | `RubricScorer` |
| `input_status`      | formalized/incomplete/…  | `RubricScorer._infer_input_status` |
| `mapping_path`      | legata/colreg-fallback   | Step02 routing        |
| `failure_reasons`   | list[str]      | Step05 + `RubricScorer` |
| `remediation_hints` | list[str]      | Step05 + `RubricScorer` |
| `score_breakdown`   | object         | `RubricScorer`       |

## 100-Point Rubric (from docs/SCORING.md)

| Dimension              | Points | Verification method              |
|------------------------|--------|----------------------------------|
| Syntax                 | 10     | RMC exit code (parse + compile)  |
| Semantic Alignment     | 55     | Mutation score × 0.50 + vacuity bonus (5 pts) |
| Verification Outcome   | 25     | RMC successful property check    |
| Hallucination Penalty  | 10     | Symbol-diffing (detect_hallucinations) |

Scoring is performed BEFORE this agent — the coordinator passes finalized
scorecards in. This agent only aggregates and formats.

## Input Schema

| Field       | Type            | Required | Description                                          |
|-------------|-----------------|----------|------------------------------------------------------|
| `scorecards`| array or string | yes      | Array of scorecard objects, or inline JSON / `@/path/to/file` |
| `output_dir`| string          | yes      | Directory to write `report.json` and `report.md`    |

## Pipeline

```
scorecards (from coordinator)
  │
  ├─► ReportGenerator.add_scorecard() × N
  │
  ├─► ReportGenerator.finalize()
  │     ├─ score_mean, score_min, score_max
  │     ├─ rules_passed, rules_failed, success_rate
  │     ├─ status_counts, fallback_usage_count, blocked_rules_count
  │     └─ top_failure_reasons, aggregate_remediation_hints
  │
  ├─► write {output_dir}/report.json  (via safe_path)
  ├─► write {output_dir}/report.md    (via safe_path)
  │
  └─► emit contract
```

## Output Contract (success)

```json
{
  "status": "ok",
  "report_path":    "/path/to/output/report.json",
  "report_md_path": "/path/to/output/report.md",
  "summary": {
    "total_rules":          1,
    "rules_passed":         1,
    "rules_failed":         0,
    "score_mean":           100.0,
    "score_min":            100,
    "score_max":            100,
    "success_rate":         100.0,
    "fallback_usage_count": 0,
    "blocked_rules_count":  0
  }
}
```

## Error Envelope

```json
{
  "status":  "error",
  "phase":   "step08",
  "agent":   "reporting-agent",
  "message": "Human-readable description of failure"
}
```

Emit on: invalid/escaped `output_dir`, scorecard parse failure, file write
failure, or schema validation violation.

## Output Patch (for coordinator)

- `workflow_summary.step08`
- `report_path` — for downstream archival
- `report_md_path` — for human review
- `summary` — aggregate statistics
