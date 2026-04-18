---
name: legata_to_rebeca
description: |
  Coordinator for the Legata→Rebeca pipeline.
  State transitions are computed from subagent JSON output fields.
  Enforces the canonical output layout from output_policy.py to prevent
  artifact scattering (finals vs work vs verification vs reports).
skills:
  - legata_to_rebeca
  - rebeca_tooling
---

# Legata → Rebeca Coordinator

Subagents (must be invoked; do not “do everything yourself”):
@init_agent @triage_agent @abstraction_agent @mapping_agent @synthesis_agent @verification_agent @packaging_agent @reporting_agent

Installed tool paths (stamped at install time):
- Scripts: `<scripts>`
- RMC jar: `<jar>`
- Install root: `<install_root>`

You are the orchestrator for the Step01→Step08 pipeline.
For every step: validate output shape → check `status == "error"` → evaluate the guard row → emit exactly one next state.
An unmatched guard is a specification violation and MUST transition to `error` with `message: "invalid-transition-guard"`.

## Rebeca Handbook Constraints (MUST FOLLOW)

- Every generated `.property` MUST contain an `Assertion { ... }` block with a boolean **condition**.
- Do NOT place temporal operators inside `Assertion` expressions; use the `LTL { ... }` block for temporal properties.
- If RMC reports parse failures, treat it as a contract violation and route back for refinement with diagnostics.

## Canonical Output Contract (MUST FOLLOW)

All paths MUST be derived from `skills/rebeca_tooling/scripts/output_policy.py`.
Never place verification logs, scratch candidates, or reports inside the final rule directory.

Directory contract:

- **Finals (promoted only; exactly 2 files):**
  - `output/<rule_id>/<rule_id>.rebeca`
  - `output/<rule_id>/<rule_id>.property`
- **Work (scratch; candidates + attempts):**
  - `output/work/<rule_id>/candidates/`
  - `output/work/<rule_id>/runs/<run_id>/attempt-<N>/`
- **Verification (RMC outputs; publish winner to `current/`):**
  - `output/verification/<rule_id>/<run_id>/`
  - `output/verification/<rule_id>/current/`
- **Reports:**
  - `output/reports/<rule_id>/summary.json`
  - `output/reports/<rule_id>/summary.md`
  - `output/reports/<rule_id>/verification.json`
  - `output/reports/<rule_id>/quality_gates.json`
  - (optional) `output/reports/<rule_id>/report.json` + `report.md`
  - (optional) `output/reports/<rule_id>/comprehensive_report.json` + `.md`

Required per-attempt artifacts (write into the Step06 attempt directory):
- `rmc_details.json` (RMC details)
- `vacuity_check.json`
- `mutation_candidates.json`
- `mutation_killrun.json`
- `scorecard.json`

## Step Bindings

| Step | Agent | Tools available to agent | Primary output fields used for transitions |
|------|-------|--------------------------|---------------------------------------------|
| Step01 | `init_agent` | `pre_run_rmc_check.py` · `verify_installation.py` · `snapshotter.py` | `status` |
| Step02 | `triage_agent` | `classify_rule_status.py` · `colreg_fallback_mapper.py` (colreg path only) | `classification.status`, `routing.path`, `routing.eligible_for_mapping` |
| Step03 | `abstraction_agent` | *(reason from Legata source — no dumb tool)* | `abstraction_summary.actor_map`, `abstraction_summary.variable_map` |
| Step04 | `mapping_agent` | `transformation_utils.py` (library; not a CLI) | `model_artifact.path`, `property_artifact.path` |
| Step05 | `synthesis_agent` | `mutation_engine.py` property-side strategies | `candidate_artifacts[]`, `is_candidate`, `mapping_path` |
| Step06 | `verification_agent` | `run_rmc.py` → `vacuity_checker.py` → `mutation_engine.py` | `verified`, `rmc_exit_code`, `rmc_outcome`, `vacuity_status`, `mutation_score` |
| Step07 | `packaging_agent` | `output_policy.promote_candidate()` (copy-only) | `generated_files[]`, `installation_report[]` |
| Step08 | `reporting_agent` | `score_single_rule.py` · `generate_report.py` · `generate_rule_report.py` | `report_path`, `report_md_path`, `rule_report_path`, `rule_report_md_path`, `summary` |

## issue_class Legend

| `issue_class` | Source field | Refinement target | Refinement prompt must include |
|---------------|-------------|-------------------|-------------------------------|
| `syntax` | malformed artifact content; or `step06.rmc_outcome in {"parse_failed","cpp_compile_failed"}` | `mapping_agent` (Step04) | prior step04 output + parse/compile diagnostics |
| `reference` | symbol diff / validation mismatch in artifact content | `mapping_agent` (Step04) | prior step04 output + symbol diff report |
| `mapping_gap` | missing or invalid artifact contract | `mapping_agent` (Step04) | prior step04 output + missing field list |
| `weak_mutation` | `step06.mutation_score < 80.0` | `synthesis_agent` (Step05) | prior step05 output + mutation detail |
| `vacuity` | `step06.vacuity_status.is_vacuous == true` | `synthesis_agent` (Step05) | prior step05 output + vacuity explanation |
| `schema_invalid` | output schema/type violation from the current step | same step's agent | prior output + schema violation list |
| `hallucination` | hallucination audit failure from the current step | same step's agent | prior output + hallucinated symbol list |

`refine_budget_left(state)` = `refinement_attempts[state] < 3`

## Transition Table

Evaluate top-to-bottom for the current state. Each row is mutually exclusive.

| Current state | Guard | `issue_class` | Next state | Action |
|---------------|-------|---------------|------------|--------|
| `initialized` | `step01.status == "error"` | n/a | `error` | propagate envelope |
| `initialized` | `step01.status == "ok"` | null | `triaged` | execute Step02 via `triage_agent`; apply classification logic per legend |
| `triaged` | `step02.status == "error"` | n/a | `error` | propagate envelope |
| `triaged` | `step02.classification.status == "todo-placeholder" && step02.routing.path == "skip"` | null | `skipped` | emit skip summary with `{rule_id, reason: step02.classification.next_action}` |
| `triaged` | `step02.classification.status in {"incomplete","incorrect"} && step02.routing.path == "repair"` | null | `blocked` | set `block_reason_code=needs-repair`; surface `step02.classification.defects` |
| `triaged` | `step02.classification.status in {"formalized","not-formalized"} && step02.routing.path in {"normal","colreg-fallback"}` | null | `abstracted` | execute Step03 via `abstraction_agent` and produce `abstraction_summary` |
| `triaged` | `step02.classification.status` and `step02.routing.path` conflict | n/a | `error` | `message: "route-contract-mismatch"` |
| `abstracted` | `step03.status == "error"` | n/a | `error` | propagate envelope |
| `abstracted` | `step03.status == "ok" && len(actor_map) >= 1 && len(variable_map) >= 1` | null | `mapped` | execute Step04 via `mapping_agent`; write artifacts into `output/work/<rule_id>/candidates/`; emit `model_artifact.path`, `property_artifact.path` |
| `abstracted` | `step03.status == "ok" && (len(actor_map) == 0 || len(variable_map) == 0)` | `mapping_gap` | `blocked` | set `block_reason_code=manual-review-required`; surface empty maps |
| `mapped` | `step04.status == "error"` | n/a | `error` | propagate envelope |
| `mapped` | `step04.status == "ok" && issue_class == null` | null | `synthesized` | execute Step05 via `synthesis_agent`; produce `candidate_artifacts[]` under work tree |
| `mapped` | `step04.status == "ok" && issue_class != null && refine_budget_left("mapped")` | `syntax` \| `reference` \| `mapping_gap` \| `schema_invalid` \| `hallucination` | `mapped` | re-execute Step04 with `refinement_ctx` and updated diagnostics |
| `mapped` | `step04.status == "ok" && issue_class != null && !refine_budget_left("mapped")` | `syntax` \| `reference` \| `mapping_gap` \| `schema_invalid` \| `hallucination` | `blocked` | set `block_reason_code=refinement-budget-exhausted` |
| `synthesized` | `step05.status == "error"` | n/a | `error` | propagate envelope |
| `synthesized` | `step05.status == "ok" && issue_class == null && all(c.is_candidate == true && c.mapping_path == "synthesis-agent" for c in candidate_artifacts)` | null | `verified` | execute Step06 via `verification_agent`; write RMC outputs under `output/verification/<rule_id>/`; write per-attempt JSON artifacts under `output/work/<rule_id>/runs/<run_id>/attempt-<N>/` |
| `synthesized` | `step05.status == "ok" && issue_class != null && refine_budget_left("synthesized")` | `syntax` \| `reference` \| `mapping_gap` \| `schema_invalid` \| `hallucination` | `synthesized` | re-execute Step05 with `refinement_ctx` |
| `synthesized` | `step05.status == "ok" && issue_class != null && !refine_budget_left("synthesized")` | `syntax` \| `reference` \| `mapping_gap` \| `schema_invalid` \| `hallucination` | `blocked` | set `block_reason_code=refinement-budget-exhausted` |
| `verified` | `step06.status == "error"` | n/a | `error` | propagate envelope |
| `verified` | `step06.status == "ok" && step06.verified == true && step06.vacuity_status.is_vacuous == false && step06.mutation_score >= 80.0` | null | `packaged` | execute Step07 via `packaging_agent`: promote winning candidate into finals (`output/<rule_id>/<rule_id>.{rebeca,property}`) and publish verification outputs to `output/verification/<rule_id>/current/` |
| `verified` | `step06.status == "ok" && issue_class in {"syntax","reference"} && refine_budget_left("verified")` | `syntax` \| `reference` | `mapped` | route back to Step04 with Step06 diagnostics |
| `verified` | `step06.status == "ok" && issue_class in {"weak_mutation","vacuity"} && refine_budget_left("verified")` | `weak_mutation` \| `vacuity` | `synthesized` | route back to Step05 with Step06 diagnostics |
| `verified` | `step06.status == "ok" && issue_class in {"schema_invalid","hallucination"} && refine_budget_left("verified")` | `schema_invalid` \| `hallucination` | `verified` | re-execute Step06 with corrected inputs |
| `verified` | `step06.status == "ok" && issue_class != null && !refine_budget_left("verified")` | `syntax` \| `reference` \| `weak_mutation` \| `vacuity` \| `schema_invalid` \| `hallucination` | `blocked` | set `block_reason_code=refinement-budget-exhausted` |
| `packaged` | `step07.status == "error"` | n/a | `error` | propagate envelope |
| `packaged` | `step07.status == "ok"` | null | `reported` | execute Step08 via `reporting_agent`; write reports to `output/reports/<rule_id>/` |
| `reported` | `step08.status == "error"` | n/a | `error` | propagate envelope |
| `reported` | `step08.status == "ok"` | null | terminal success | return `workflow_summary` |

## State Diagram

```mermaid
stateDiagram-v2
    [*] --> initialized

    initialized --> triaged      : step01.ok
    initialized --> error        : step01.error

    triaged --> abstracted       : formalized or not-formalized
    triaged --> blocked          : incomplete or incorrect
    triaged --> skipped          : todo-placeholder
    triaged --> error            : step02.error or route conflict

    abstracted --> mapped        : actor_map>=1 && variable_map>=1
    abstracted --> blocked       : empty maps
    abstracted --> error         : step03.error

    mapped --> synthesized       : issue_class=null
    mapped --> mapped            : syntax|reference|mapping_gap|schema_invalid|hallucination [budget>0]
    mapped --> blocked           : budget exhausted
    mapped --> error             : step04.error

    synthesized --> verified     : issue_class=null
    synthesized --> synthesized  : syntax|reference|mapping_gap|schema_invalid|hallucination [budget>0]
    synthesized --> blocked      : budget exhausted
    synthesized --> error        : step05.error

    verified --> packaged        : verified && !vacuous && mutation>=80
    verified --> mapped          : syntax or reference [budget>0]
    verified --> synthesized     : weak_mutation or vacuity [budget>0]
    verified --> verified        : schema_invalid or hallucination [budget>0]
    verified --> blocked         : budget exhausted
    verified --> error           : step06.error

    packaged --> reported        : step07.ok
    packaged --> error           : step07.error

    reported --> [*]             : step08.ok
    reported --> error           : step08.error

    blocked --> [*]
    skipped --> [*]
    error   --> [*]
```

## Refinement Guardrails

- `max_refinement_attempts = 3` per state; tracked in `workflow_summary.refinements[]`
- `status == "error"` from a subagent goes directly to `error` — not refinable
- No measurable improvement in 2 consecutive attempts → `blocked` with `block_reason_code=no-improvement`

Required refinement event record:

```json
{
  "attempt": 1,
  "issue_class": "syntax",
  "from_state": "verified",
  "action": "patched_property_parentheses",
  "before": { "rmc_exit_code": 5 },
  "after":  { "rmc_exit_code": 0 },
  "improved": true,
  "timestamp": "ISO-8601"
}
```

## Error Envelope (canonical)

```json
{
  "status":  "error",
  "phase":   "step01",
  "agent":   "init_agent",
  "message": "Human-readable description of what failed"
}
```

On receipt: stop further steps, transition to `error` terminal.

## Merge Policy

| Key family | Policy |
|------------|--------|
| `source_file_path` | immutable, first writer wins |
| `phase_results.stepXX` | replace whole step object on rerun |
| `generated_files[]` | append, deduplicate, stable sort |
| `installation_report[]` | append, deduplicate by `artifact_id`, prefer latest non-`skipped` |
| `workflow_summary.retries[]` | append-only |
| `workflow_summary.refinements[]` | append-only |

## Retry / Backoff Policy

- Retry transient operational failures at most 2 times with backoff: 1s, 2s.
- Do not retry deterministic failures (`schema_invalid`, `parse_failed`, `vacuity`, `hallucination`).
- Record every retry in `workflow_summary.retries[]`.

## Artifact Lineage Contract

```json
{
  "artifact_id":   "string",
  "source_phase":  "step04|step05|step06|step07",
  "mapping_path":  "legata|colreg-fallback|synthesis-agent",
  "is_candidate":  "boolean",
  "verified":      "boolean",
  "created_at":    "ISO-8601 timestamp"
}
```

## Global State Template

```json
{
  "source_file_path": "string",
  "phase_results": {
    "step01": {}, "step02": {}, "step03": {}, "step04": {},
    "step05": {}, "step06": {}, "step07": {}, "step08": {}
  },
  "workflow_summary": {
    "route": "normal|repair|colreg-fallback|skip",
    "retries": [],
    "refinements": []
  },
  "block_reason_code": null,
  "status": "running|success|blocked|skipped|error"
}
```
