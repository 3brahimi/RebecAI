# Usage Guide

Complete workflow execution examples for the legata-to-rebeca agent.

## Basic Usage

### Transform a Single Rule

```
@legata-to-rebeca Transform legata/Rule-22-Equipment-Range.legata to Rebeca.
Reference model: src/PromptingExperimentDoc/SimulationModelCode.rebeca
Reference property: src/PromptingExperimentDoc/SimulationModelCode.property
```

**Expected output:**
- `output/Rule-22-Equipment-Range.rebeca` - Generated model
- `output/Rule-22-Equipment-Range.property` - Generated property
- `output/system.rebeca` - Refined reference model
- `output/system.property` - Refined reference properties

### Transform with Verification

```
@legata-to-rebeca
Transform legata/Rule-22-Equipment-Range.legata to Rebeca.
Reference model: src/PromptingExperimentDoc/SimulationModelCode.rebeca
Reference property: src/PromptingExperimentDoc/SimulationModelCode.property
Run RMC verification and report results.
```

**Expected output:**
- Model and property files (as above)
- `output/verification_output/model.out` - Compiled executable
- `output/verification_output/rmc_stdout.log` - RMC output
- `output/scorecard.json` - Scoring results

### Transform with Fallback

```
@legata-to-rebeca Transform Rule-23 to Rebeca. If Legata is incomplete, use COLREG text fallback.
Reference model: src/PromptingExperimentDoc/SimulationModelCode.rebeca
Reference property: src/PromptingExperimentDoc/SimulationModelCode.property
```

**When to use:**
- Legata file is incomplete or incorrect
- Need provisional property from COLREG text
- Want to attempt transformation despite missing formalization

## Advanced Usage

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

**Expected output:**
- Per-rule model and property files
- Per-rule scorecards
- `output/aggregate_report.json` - Summary report
- `output/aggregate_report.md` - Markdown report

### Triage and Classify

```
@legata-to-rebeca
Classify all Legata rules in legata/ directory.
For incomplete or incorrect rules, suggest repairs.
For not-formalized rules, attempt COLREG fallback mapping.
```

**Expected output:**
- Classification results (formalized/incomplete/incorrect/not-formalized/todo)
- Repair suggestions for problematic rules
- COLREG fallback mappings where applicable

### Custom Timeout

```
@legata-to-rebeca
Transform legata/Rule-22-Equipment-Range.legata to Rebeca.
Reference model: src/PromptingExperimentDoc/SimulationModelCode.rebeca
Reference property: src/PromptingExperimentDoc/SimulationModelCode.property
Run RMC verification with 300-second timeout.
```

**When to use:**
- Complex models requiring longer verification time
- Default 120-second timeout is insufficient

## Python Library Usage

### Import and Setup

```python
import sys
from pathlib import Path

# Add rebeca-tooling skill to path
tooling_skill = Path("~/.agents/skills/rebeca-tooling").expanduser()
sys.path.insert(0, str(tooling_skill))

from lib import (
    run_rmc,
    RuleStatusClassifier,
    COLREGFallbackMapper,
    score_single_rule,
    generate_report
)
```

### Run Verification

```python
from lib import pre_run_rmc_check, run_rmc

# Ensure RMC available
pre_run_rmc_check()

# Run verification
result = run_rmc(
    jar="~/.agents/rmc/rmc.jar",
    model="output/Rule-22.rebeca",
    property_file="output/Rule-22.property",
    output_dir="output/verification",
    timeout_seconds=120
)

print(f"Exit code: {result['exit_code']}")
print(f"Stdout: {result['stdout']}")
print(f"Stderr: {result['stderr']}")
```

### Classify Rule Status

```python
from lib import RuleStatusClassifier

classifier = RuleStatusClassifier()
status = classifier.classify("legata/Rule-22-Equipment-Range.legata")

print(f"Status: {status['status']}")
print(f"Reason: {status['reason']}")
```

### Score Transformation

```python
from lib import score_single_rule

score = score_single_rule(
    rule_id="Rule-22",
    verify_status="pass",
    syntax_correct=True,
    semantic_aligned=True
)

print(f"Total score: {score['total_score']}/100")
print(f"Breakdown: {score['breakdown']}")
```

### Generate Report

```python
from lib import generate_report

generate_report(
    input_scores="output/scorecards.json",
    output_dir="output/reports",
    format="both"  # json and markdown
)
```

## CLI Usage

### Setup

```bash
python3 setup.py
```

### Run Verification

```bash
python3 ~/.agents/skills/rebeca-tooling/lib/run_rmc.py \
  --jar ~/.agents/rmc/rmc.jar \
  --model output/Rule-22.rebeca \
  --property output/Rule-22.property \
  --output-dir output/verification \
  --timeout-seconds 120
```

### Classify Rule

```bash
python3 ~/.agents/skills/rebeca-tooling/lib/classify_rule_status.py \
  --legata-path legata/Rule-22-Equipment-Range.legata \
  --output-json
```

### Score Rule

```bash
python3 ~/.agents/skills/rebeca-tooling/lib/score_single_rule.py \
  --rule-id Rule-22 \
  --verify-status pass \
  --output-json
```

### Generate Report

```bash
python3 ~/.agents/skills/rebeca-tooling/lib/generate_report.py \
  --input-scores output/scorecards.json \
  --output-dir output/reports \
  --format both
```

## Understanding Output

### Verification Exit Codes

- `0`: Success - Model and property verified
- `3`: Timeout - Verification exceeded time limit
- `4`: C++ compilation failed - RMC generated invalid C++
- `5`: Parse failed - Syntax error in `.rebeca` or `.property`

### Counterexample vs Error

**Counterexample:**
- Property violated by model
- Model is unsafe (not a syntax error)
- Need to refine model or property

**Parse Error:**
- Syntax error in `.rebeca` or `.property`
- Translation is broken
- RMC cannot check anything

### Scoring Interpretation

| Score | Interpretation |
|-------|----------------|
| 90-100 | Excellent - Verified and semantically aligned |
| 70-89 | Good - Syntax correct, minor semantic issues |
| 40-69 | Fair - Syntax correct, verification failed |
| 0-39 | Poor - Syntax errors or parse failures |

## Next Steps

- [Architecture Guide](architecture.md) - Understand system design
- [API Reference](api-reference.md) - Complete function signatures
- [Troubleshooting](../guides/troubleshooting.md) - Common issues and fixes
