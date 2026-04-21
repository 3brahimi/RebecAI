---
name: reporting_agent
description: |
  Step08 specialist for aggregate scoring and report generation.
  Wraps ReportGenerator (generate_report.py) to produce summary.json
  and summary.md from coordinator-supplied per-rule scorecards, and
  generate_rule_report.py to produce comprehensive_report.json/.md.
  Also writes verification.json and quality_gates.json (all four are
  canonical Step08 outputs required by Gate 0).
schema: skills/rebeca_tooling/schemas/reporting-agent.schema.json
skills:
  - rebeca_tooling
  - rebeca_hallucination
  - rebeca_handbook
---

# Step08 Subagent: Scoring and Reporting

## Goal

Consume per-rule scorecards assembled by the coordinator (from Step05 outputs),
finalize aggregate metrics via `ReportGenerator`, write the four canonical report
files to `output/reports/<rule_id>/`, then generate a per-rule comprehensive
report from the packaged rule folder.

Canonical Step08 outputs (all four required by Gate 0):
1. `summary.json` — aggregate scorecard summary (JSON)
2. `summary.md` — aggregate scorecard summary (Markdown)
3. `verification.json` — per-rule verification outcomes
4. `quality_gates.json` — gate pass/fail results per rule

All report outputs are versioned and deterministic.

## Determinism Rules

- Sort input scorecards by `source_file_path` ascending before aggregation.
- Sort `top_failure_reasons` and `aggregate_remediation_hints` lexicographically.
- Emit stable JSON key order and stable markdown section order.
- Include `report_schema_version` in output for forward-compatible consumers.

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

## 100-Point Rubric

| Dimension              | Points | Verification method              |
|------------------------|--------|----------------------------------|
| Syntax                 | 10     | RMC exit code (parse + compile)  |
| Semantic Alignment     | 55     | Mutation score × 0.50 + vacuity bonus (5 pts) |
| Verification Outcome   | 25     | RMC successful property check    |
| Hallucination Penalty  | 10     | Symbol-diffing (detect_hallucinations) |

Scoring is performed BEFORE this agent — the coordinator passes finalized
scorecards in. This agent only aggregates and formats.

## Output Schema

```json
{
  "status": "ok",
  "summary_path":    "/path/to/output/reports/Rule-22/summary.json",
  "summary_md_path": "/path/to/output/reports/Rule-22/summary.md",
  "report_schema_version": "1.1.0",
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

## Input Schema

| Field       | Type            | Required | Description                                          |
|-------------|-----------------|----------|------------------------------------------------------|
| `scorecards`| array or string | yes      | Array of scorecard objects, or inline JSON / `@/path/to/file` |
| `output_dir`| string          | yes      | **Report root directory**. Prefer passing a path whose basename is `reports` (e.g. `output/reports`). |

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
  ├─► run generate_report.py --output-dir {output_dir}
  │     ├─ (single) writes: {output_dir}/{rule_id}/summary.json + summary.md
  │     ├─ (single) writes: {output_dir}/{rule_id}/verification.json
  │     ├─ (single) writes: {output_dir}/{rule_id}/quality_gates.json
  │     └─ (multi)   writes: {output_dir}/aggregate/summary.json + summary.md
  │                          {output_dir}/aggregate/verification.json
  │                          {output_dir}/aggregate/quality_gates.json
  ├─► run generate_rule_report.py --rule-dir {rule_output_dir}
  │     ├─ write {output_dir}/{rule_id}/comprehensive_report.json
  │     └─ write {output_dir}/{rule_id}/comprehensive_report.md
  │
  └─► emit contract
```

## Output Contract (success)

```json
{
  "status": "ok",
  "summary_path":    "/path/to/output/reports/Rule-22/summary.json",
  "summary_md_path": "/path/to/output/reports/Rule-22/summary.md",
  "rule_report_path": "/path/to/output/reports/Rule-22/comprehensive_report.json",
  "rule_report_md_path": "/path/to/output/reports/Rule-22/comprehensive_report.md",
  "report_schema_version": "1.1.0",
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
  "agent":   "reporting_agent",
  "message": "Human-readable description of failure"
}
```

Emit on: invalid/escaped `output_dir`, scorecard parse failure, file write
failure, or schema validation violation.

## Canonical Artifact Persistence (REQUIRED)

After all report files are written and the output contract is assembled, persist the canonical pointer artifact atomically **before** returning output to the coordinator:

```bash
python skills/rebeca_tooling/scripts/artifact_writer.py \
  --rule-id <source_file_path> --step step08_reporting \
  --data '<output_contract_json>' [--base-dir output]
```

The `step08_reporting.json` artifact is required by Gate 0. It must contain `summary_path` and `summary.{total_rules,rules_passed,score_mean}`. Gate 0 also verifies that the four required report files (`summary.json`, `summary.md`, `verification.json`, `quality_gates.json`) exist under `output/reports/<rule_id>/`.

## Output Patch (for coordinator)

- `workflow_summary.step08`
- `summary_path` — for downstream archival
- `summary_md_path` — for human review
- `report_schema_version` — schema compatibility pin
- `summary` — aggregate statistics
- `rule_report_path` — comprehensive per-rule JSON report path
- `rule_report_md_path` — comprehensive per-rule markdown report path
