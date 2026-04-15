# legata_to_rebeca Agent

Transforms maritime safety rules from Legata formal specification into verifiable Rebeca actor models.

## Capabilities

- **8-phase prescribed workflow** (WF-01 through WF-08)
- **Rule quality triage** - Classify formalization status
- **COLREG fallback mapping** - Handle incomplete specifications
- **RMC model checking** - Automated verification with C++ compilation
- **100-point scoring rubric** - Assess transformation quality
- **Aggregate reporting** - JSON and Markdown reports

## Required Inputs

The agent requires three inputs for each transformation:

1. **Legata or COLREG rule file** - The formal specification to transform
2. **Reference Rebeca model** (`system.rebeca`) - Base model subject to refinement/append
3. **Reference property file** (`system.property`) - Base properties subject to refinement/append

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

### Triage and Classify

```
@legata_to_rebeca
Classify all Legata rules in legata/ directory.
For incomplete or incorrect rules, suggest repairs.
For not-formalized rules, attempt COLREG fallback mapping.
```

## Workflow Phases

| Phase | Name | Description | Output |
|-------|------|-------------|--------|
| WF-01 | Toolchain and Inputs Initialization | Validate required sources, pin RMC version, fail fast on missing inputs | Validated inputs + RMC version |
| WF-02 | Clause Eligibility and Triage | Classify rules: formalized/incomplete/incorrect/not-formalized/todo-placeholder | Classification + defect list |
| WF-03 | Abstraction and Discretization Setup | Define bounded representations, map COLREG units to discrete variables | Naming conventions + variable map |
| WF-04 | Manual Mapping Core | Extract Legata clause context, align state variables, encode assertions `(!condition \|\| exclude \|\| assure)` | `.rebeca` model + `.property` file |
| WF-05 | Verification and Counterexample Iteration | Run RMC model checking, classify failure root cause, iterate until success or explicit block | Verification result (pass/fail/timeout/error) |
| WF-06 | Optional LLM-Assisted Lane | Generate candidate properties, always validate via WF-05, apply 100-point rubric | Candidate property (requires WF-05 validation) |
| WF-07 | Packaging and Automation | Generate agent/skill/scripts, ensure runtime isolation, embed constraints inline | Packaged artifacts |
| WF-08 | Scoring and Reporting | Per-rule scorecards (100-point rubric), aggregate reporting, no-silent-skip enforcement | `scorecard.json` + `report.json` / `report.md` |

## Expected Output

The agent refines/appends to reference files and produces:

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
└── aggregate_report.json               # Summary report
```

## Scoring Rubric

The agent applies a 100-point scoring rubric:

| Dimension | Points | Criterion |
|-----------|--------|-----------|
| **Syntax correctness** | 10 | Model and property parse without RMC errors |
| **Semantic alignment** | 55 | Transformation faithfully preserves Legata/COLREG rule intent |
| **Verification outcome** | 25 | RMC verification passes (no counterexample) |
| **Hallucination penalty** | −10 | Deducted for fabricated actors, variables, or rule references |

Total maximum: **100 points**. Scores are computed by `RubricScorer` in `scripts/score_single_rule.py`.

## Skills Used

The agent leverages three skills:

- **[legata_to_rebeca](../skills/legata_to_rebeca.md)** - Workflow guidance
- **[rebeca-handbook](../skills/rebeca-handbook.md)** - Modeling best practices
- **[rebeca-tooling](../skills/rebeca-tooling.md)** - Python library for automation

## Installation

See [Installation Guide](../guides/installation.md) for setup instructions.

## Troubleshooting

See [Troubleshooting Guide](../guides/troubleshooting.md) for common issues and fixes.
