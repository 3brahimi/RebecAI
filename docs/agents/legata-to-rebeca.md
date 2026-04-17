# legata_to_rebeca Agent

Coordinator for the Legata→Rebeca pipeline. Orchestrates eight specialist subagents through a prescribed Step01–Step08 workflow.

## Architecture: Multi-Agent Orchestration (MAO)

`legata_to_rebeca` is a **coordinator**, not a monolithic agent. It delegates each step to a dedicated specialist subagent. Each specialist runs in its own context window, calls deterministic Python scripts via `Bash`, and emits a structured JSON contract back to the coordinator.

```
legata_to_rebeca (coordinator)
├── Step01 → init_agent
├── Step02 → triage_agent
├── Step03 → abstraction_agent
├── Step04 → mapping_agent
├── Step05 → synthesis_agent          (parallel with Step04)
├── Step06 → verification_agent
├── Step07 → packaging_agent
└── Step08 → reporting_agent
```

### Step Bindings

| Step | Agent | Dumb tools (Python scripts) |
|------|-------|----------------------------|
| Step01 | `init_agent` | `pre_run_rmc_check.py` · `verify_installation.py` · `snapshotter.py` |
| Step02 | `triage_agent` | `classify_rule_status.py` · `colreg_fallback_mapper.py` |
| Step03 | `abstraction_agent` | `classify_rule_status.py` |
| Step04 | `mapping_agent` | `run_rmc.py` |
| Step05 | `synthesis_agent` | `run_rmc.py` |
| Step06 | `verification_agent` | `run_rmc.py` · `vacuity_checker.py` · `mutation_engine.py` |
| Step07 | `packaging_agent` | `install_artifacts.py` |
| Step08 | `reporting_agent` | `score_single_rule.py` · `generate_report.py` · `generate_rule_report.py` |

Each specialist's output schema is defined in `skills/rebeca_tooling/schemas/<agent-name>.schema.json`.

## Capabilities

- **8-step prescribed workflow** (Step01 through Step08)
- **Rule quality triage** — classify formalization status
- **COLREG fallback mapping** — handle incomplete specifications
- **RMC model checking** — automated verification with C++ compilation
- **100-point scoring rubric** — assess transformation quality
- **Aggregate + comprehensive reporting** — JSON and Markdown reports (portfolio and per-rule)

## Required Inputs

The coordinator requires three inputs for each transformation:

1. **Legata or COLREG rule file** — the formal specification to transform
2. **Reference Rebeca model** (`system.rebeca`) — base model subject to refinement/append
3. **Reference property file** (`system.property`) — base properties subject to refinement/append

## Usage Examples

### Transform a Single Rule

```
@legata_to_rebeca Transform legata/Rule-22-Equipment-Range.legata to Rebeca.
Reference model: src/PromptingExperimentDoc/SimulationModelCode.rebeca
Reference property: src/PromptingExperimentDoc/SimulationModelCode.property
```

### Transform with Fallback

```
@legata_to_rebeca Transform Rule-23 to Rebeca. If Legata is incomplete, use COLREG text fallback.
Reference model: src/PromptingExperimentDoc/SimulationModelCode.rebeca
Reference property: src/PromptingExperimentDoc/SimulationModelCode.property
```

### Full Workflow with Verification

```
@legata_to_rebeca
Transform legata/Rule-22-Equipment-Range.legata to Rebeca model and property.
Reference model: src/PromptingExperimentDoc/SimulationModelCode.rebeca
Reference property: src/PromptingExperimentDoc/SimulationModelCode.property
Run RMC verification and score the result.
Generate a report with verification outcome.
```

### Batch Transformation

```
@legata_to_rebeca
Transform all rules in legata/ directory to Rebeca models.
Reference model: src/PromptingExperimentDoc/SimulationModelCode.rebeca
Reference property: src/PromptingExperimentDoc/SimulationModelCode.property
For each rule:
1. Classify formalization status
2. Refine/append to reference model and property
3. Run RMC verification
4. Score results
5. Generate aggregate report
```

## Workflow Steps

| Step | Agent | Name | Description | Primary output |
|------|-------|------|-------------|----------------|
| Step01 | `init_agent` | Toolchain and Inputs Initialization | Validate required sources, provision RMC, pin toolchain metadata, capture golden snapshot | `status`, RMC version |
| Step02 | `triage_agent` | Clause Eligibility and Triage | Classify rules: `formalized` / `incomplete` / `incorrect` / `not-formalized` / `todo-placeholder`; attach evidence and defects | Classification + defect list |
| Step03 | `abstraction_agent` | Abstraction and Discretization Setup | Extract actors and conditions from Legata, apply deterministic naming conventions, discretize to Rebeca-compatible types | Naming conventions + variable map |
| Step04 | `mapping_agent` | Manual Mapping Core | Extract Legata clause context, align state variables, encode assertions `(!condition \|\| exclude \|\| assure)` | `.rebeca` model + `.property` file |
| Step05 | `synthesis_agent` | LLM-Assisted Candidate Generation | Generate candidate properties in parallel with Step04; all outputs tagged `is_candidate=true`, must be routed to Step06 | Candidate property |
| Step06 | `verification_agent` | Verification and Counterexample Iteration | Run RMC model checking, vacuity check, mutation scoring; iterate until pass or explicit block | Verification result + mutation score |
| Step07 | `packaging_agent` | Packaging and Automation | Collect pipeline artifacts, build finalized manifest, emit per-artifact installation report | Packaged artifacts |
| Step08 | `reporting_agent` | Scoring and Reporting | Per-rule scorecards (100-point rubric), aggregate reporting, comprehensive per-rule reporting, no-silent-skip enforcement | `scorecard.json` + `report.json` / `report.md` + `comprehensive_report.json` / `comprehensive_report.md` |

## Expected Output

The coordinator refines/appends to reference files and produces:

```
output/
├── system.rebeca                       # Refined model (appended actors/handlers)
├── system.property                     # Refined properties (appended assertions)
├── Rule-22-Equipment-Range.rebeca      # Rule-specific model fragment
├── Rule-22-Equipment-Range.property    # Rule-specific property
├── verification_output/
│   ├── model.out                       # Compiled executable
│   ├── rmc_stdout.log                  # RMC output
│   └── rmc_stderr.log                  # Error logs
├── scorecard.json                      # Per-rule scoring
├── aggregate_report.json               # Summary report
└── comprehensive_report.json           # Detailed per-rule report
```

## Scoring Rubric

| Dimension | Points | Criterion |
|-----------|--------|-----------|
| **Syntax correctness** | 10 | Model and property parse without RMC errors |
| **Semantic alignment** | 55 | Mutation Score × 0.50 + vacuity pass bonus (5 pts) |
| **Verification outcome** | 25 | RMC verification passes (no counterexample) |
| **Hallucination penalty** | −10 | Deducted for fabricated actors, variables, or rule references |

Total maximum: **100 points**. See [SCORING.md](../SCORING.md) for the full rubric specification.

## Agent Frontmatter

All subagents follow the standard Claude Code / Gemini CLI sub-agent format:

```yaml
---
name: triage_agent
description: |
  Step02 specialist: ...
schema: skills/rebeca_tooling/schemas/triage-agent.schema.json
skills:
  - rebeca_tooling
---
```

- `schema` — internal contract pointer used by the coordinator for output validation (Claude Code tolerates unknown keys; stripped for Gemini CLI)
- `skills` — valid Claude Code key; injects the skill's `SKILL.md` content into the subagent's system prompt at startup
- `tools` — omitted on all agents; subagents inherit all tools from the coordinator session (including `Bash` needed to call Python scripts)

## Skills Used

| Skill | Used by agents |
|-------|---------------|
| `rebeca_tooling` | All specialists |
| `rebeca_handbook` | `abstraction_agent`, `mapping_agent`, `synthesis_agent`, `verification_agent`, `reporting_agent` |
| `legata_to_rebeca` | Coordinator only |

## Installation

See [Installation Guide](../guides/installation.md) for setup instructions.

## Troubleshooting

See [Troubleshooting Guide](../guides/troubleshooting.md) for common issues and fixes.
