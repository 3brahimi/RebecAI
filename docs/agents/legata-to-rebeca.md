# legata-to-rebeca Agent

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
@legata-to-rebeca Transform legata/Rule-22-Equipment-Range.legata to Rebeca.
Reference model: src/PromptingExperimentDoc/SimulationModelCode.rebeca
Reference property: src/PromptingExperimentDoc/SimulationModelCode.property
```

### Transform with Fallback

```
@legata-to-rebeca Transform Rule-23 to Rebeca. If Legata is incomplete, use COLREG text fallback.
Reference model: src/PromptingExperimentDoc/SimulationModelCode.rebeca
Reference property: src/PromptingExperimentDoc/SimulationModelCode.property
```

### Full Workflow with Verification

```
@legata-to-rebeca
Transform legata/Rule-22-Equipment-Range.legata to Rebeca model and property.
Reference model: src/PromptingExperimentDoc/SimulationModelCode.rebeca
Reference property: src/PromptingExperimentDoc/SimulationModelCode.property
Run RMC verification and score the result.
Generate a report with verification outcome.
```

### Batch Transformation

```
@legata-to-rebeca
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
@legata-to-rebeca
Classify all Legata rules in legata/ directory.
For incomplete or incorrect rules, suggest repairs.
For not-formalized rules, attempt COLREG fallback mapping.
```

## Workflow Phases

| Phase | Description | Output |
|-------|-------------|--------|
| WF-01 | Triage rule status | Classification (formalized/incomplete/incorrect/not-formalized/todo) |
| WF-02 | Transform Legata → Rebeca | `.rebeca` model file |
| WF-03 | Generate property | `.property` file |
| WF-04 | COLREG fallback (if needed) | Provisional property from COLREG text |
| WF-05 | Run RMC verification | Verification result (pass/fail/timeout/error) |
| WF-06 | Score transformation | 100-point scorecard |
| WF-07 | Generate per-rule report | JSON scorecard |
| WF-08 | Generate aggregate report | JSON and Markdown summary |

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

- **Syntax correctness** (40 points) - Model and property parse without errors
- **Semantic alignment** (30 points) - Transformation preserves rule intent
- **Verification outcome** (30 points) - RMC verification passes

## Skills Used

The agent leverages three skills:

- **[legata-to-rebeca](../skills/legata-to-rebeca.md)** - Workflow guidance
- **[rebeca-handbook](../skills/rebeca-handbook.md)** - Modeling best practices
- **[rebeca-tooling](../skills/rebeca-tooling.md)** - Python library for automation

## Installation

See [Installation Guide](../guides/installation.md) for setup instructions.

## Troubleshooting

See [Troubleshooting Guide](../guides/troubleshooting.md) for common issues and fixes.
