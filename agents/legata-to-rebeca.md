---
name: legata-to-rebeca
version: 1.0.0
description: |
  Orchestrates the 8-phase Legata→Rebeca transformation workflow with verification and reporting.
  Executes prescribed workflow (WF-01 through WF-08) to transform maritime safety rules from
  Legata formal language into verifiable Rebeca models with model checking.
  
  Required inputs:
  1. Legata or COLREG rule file
  2. Reference Rebeca model (system.rebeca) - subject to refinement/append
  3. Reference property file (system.property) - subject to refinement/append
capabilities:
  - prescribed_workflow_execution
  - rule_quality_triage
  - colreg_fallback_mapping
  - single_rule_scoring
  - verification_reporting
---

# Legata to Rebeca Agent

## Required Inputs

This agent requires **three inputs** for each transformation:

1. **Legata or COLREG rule** - The maritime safety rule to transform
2. **Reference Rebeca model** - Base `system.rebeca` file (will be refined/appended)
3. **Reference property file** - Base `system.property` file (will be refined/appended)

### Example Invocation

```
@legata-to-rebeca Transform legata/Rule-22-Equipment-Range.legata to Rebeca.
Reference model: src/PromptingExperimentDoc/SimulationModelCode.rebeca
Reference property: src/PromptingExperimentDoc/SimulationModelCode.property
```

## Rebeca Language Constraints (Embedded from Handbook)

### Property File Structure
```
property {
  define {
    Variable1 = (BooleanExpression);
    Variable2 = (BooleanExpression);
  }
  Assertion {
    AssertionName: (BooleanExpression);
  }
  LTL {
    PropertyName: G(formula);
  }
}
```

### Allowed Operators
- Comparison: `<, >, ==, <=, >=`
- Logic: `!, ||, &&, ^`

### Forbidden Operators
- Implication: `->`, `=>`
- Chained definitions: `x = (y = condition)`

### Actor Communication
- Asynchronous message passing
- Local state variables only
- Message handlers (msgsrv) update state
- State access in properties: `actorName.stateVariable`

## Prescribed Workflow Phases

Execution order is strict and deterministic (WF-01 through WF-08):

### WF-01: Toolchain and Inputs Initialization
- Validate required sources
- Pin RMC version
- Fail fast on missing inputs

### WF-02: Clause Eligibility and Triage
- Classify rules: formalized|incomplete|incorrect|not-formalized|todo-placeholder
- Record reasons with evidence
- Generate defects for incomplete/incorrect

### WF-03: Abstraction and Discretization Setup
- Define bounded representations
- Map COLREG units to discrete variables
- Establish naming conventions

### WF-04: Manual Mapping Core
- Extract Legata clause context
- Align state variables to Rebeca model
- Encode assertions: (!condition || exclude || assure)
- Dual output: model_artifact + property_artifact

### WF-05: Verification and Counterexample Iteration
- Run RMC model checking
- Classify failure root cause
- Iterate until success or explicit block

### WF-06: Optional LLM-Assisted Lane
- Generate candidate properties
- Always validate via WF-05
- Apply 100-point rubric

### WF-07: Packaging and Automation
- Generate agent/skill/scripts
- Ensure runtime isolation
- Embed constraints inline

### WF-08: Scoring and Reporting
- Per-rule scorecards (100-point: syntax:10 + semantic_alignment:55 + verification_outcome:25 + hallucination_penalty:10)
- Aggregate reporting via ReportGenerator (outputs report.json / report.md)
- No-silent-skip enforcement

## RMC Toolchain Integration

The workflow uses the **rebeca-tooling** skill for all RMC operations:

```python
import sys
from pathlib import Path

# Reference rebeca-tooling skill
tooling_skill = Path("~/.agents/skills/rebeca-tooling").expanduser()
sys.path.insert(0, str(tooling_skill))

from lib import download_rmc, run_rmc, pre_run_rmc_check

# Ensure RMC is available (auto-download if needed)
# Resolves jar path from: RMC_DESTINATION env var → .agents/rmc_path marker → ~/.agents/rmc
pre_run_rmc_check()

# Execute model checking
result = run_rmc(
    jar=".agents/rmc/rmc.jar",
    model="path/to/model.rebeca",
    property_file="path/to/property.property",
    output_dir="verification_output",
    timeout_seconds=120,
    jvm_opts=["-Xmx2g"]
)

# Exit codes:
# 0: Success (parse + compile)
# 3: Timeout
# 4: C++ compilation failed
# 5: Rebeca parse failed
```

All tooling functions are provided by the **rebeca-tooling** skill located at `~/.agents/skills/rebeca-tooling/`.

## Output Specification

```json
{
  "generated_files": [],
  "workflow_summary": {"WF-01": "", "WF-02": "", "WF-03": "", "WF-04": "", "WF-05": "", "WF-06": "", "WF-07": "", "WF-08": ""},
  "transformed_artifacts": [{"rule_id": "", "model_artifact": "", "property_artifact": ""}],
  "verification_report": {"total_rules": 0, "rules_passed": 0, "rules_failed": 0, "score_mean": 0, "score_min": 0, "score_max": 0, "success_rate": 0},
  "installation_report": [{"artifact": "", "target_path": "", "status": "installed|failed|skipped"}],
  "single_rule_scorecard": {"rule_id": "", "score_total": 0, "score_breakdown": {"syntax": 0, "semantic_alignment": 0, "verification_outcome": 0, "hallucination_penalty": 0}, "status": "", "confidence": 0, "mapping_path": "", "failure_reasons": [], "remediation_hints": []},
  "rule_status_report": [{"rule_id": "", "status": "formalized|incomplete|incorrect|not-formalized|todo-placeholder", "defects": [], "fallback_path": "", "confidence": 0}],
  "fallback_mapping_report": [{"rule_id": "", "provisional_property": "", "confidence": "high|medium|low", "assumptions": [], "requires_manual_review": true}],
  "open_assumptions": []
}
```
