# API Reference

Complete Python library reference for `skills/rebeca_tooling/scripts/`.

## Installation

```python
import sys
from pathlib import Path

# Add rebeca_tooling skill to path
tooling_skill = Path("~/.agents/skills/rebeca_tooling").expanduser()
sys.path.insert(0, str(tooling_skill))

from scripts import *
```

## Core Functions

### download_rmc

Download RMC from GitHub releases.

```python
from scripts import download_rmc

download_rmc(
    url: str,
    dest_dir: str,
    filename: str = "rmc.jar",
    verify_checksum: bool = False,
    checksum: str | None = None
) -> dict
```

**Parameters:**
- `url` - GitHub release URL or direct JAR URL
- `dest_dir` - Destination directory for RMC
- `filename` - Output filename (default: "rmc.jar")
- `verify_checksum` - Whether to verify SHA256 checksum
- `checksum` - Expected SHA256 checksum

**Returns:**
```python
{
    "success": bool,
    "path": str,
    "error": str | None
}
```

**Example:**
```python
result = download_rmc(
    url="https://github.com/rebeca-lang/org.rebecalang.rmc/releases/latest",
    dest_dir="~/.agents/rmc"
)
```

### run_rmc

Execute RMC model checker with C++ compilation.

```python
from scripts import run_rmc

run_rmc(
    jar: str,
    model: str,
    property_file: str,
    output_dir: str,
    timeout_seconds: int = 120
) -> int
```

**Parameters:**
- `jar` - Path to RMC JAR file
- `model` - Path to `.rebeca` model file
- `property_file` - Path to `.property` file
- `output_dir` - Output directory for verification artifacts
- `timeout_seconds` - Timeout in seconds (default: 120)

**Returns:**
- `int` exit code (`0=success`, `1=invalid_inputs`, `3=timeout`, `4=compile_failed`, `5=parse_failed`)

**Example:**
```python
exit_code = run_rmc(
    jar="~/.agents/rmc/rmc.jar",
    model="output/Rule-22.rebeca",
    property_file="output/Rule-22.property",
    output_dir="output/verification",
    timeout_seconds=120
)

if exit_code == 0:
    print("Verification successful")
elif exit_code == 5:
    print("Parse error")
```

### pre_run_rmc_check

Auto-provision RMC before execution.

```python
from scripts import pre_run_rmc_check

pre_run_rmc_check(
    rmc_dir: str | None = None,
    download_if_missing: bool = True
) -> bool
```

**Parameters:**
- `rmc_dir` - RMC directory (default: `~/.agents/rmc`)
- `download_if_missing` - Auto-download if not found

**Returns:**
- `True` if RMC available, `False` otherwise

**Example:**
```python
if pre_run_rmc_check():
    result = run_rmc(...)
```

### setup.py (repository root)

Use repository-level `setup.py` for prerequisites, RMC provisioning, and artifact installation.

**Returns:**
- `0` - Success
- `1` - Prerequisites missing
- `2` - RMC download failed
- `3` - RMC verification failed
- `4` - Artifact installation failed

**Example:**
```bash
python3 setup.py
```

## Classification Functions

### RuleStatusClassifier

Classify Legata rule formalization status.

```python
from scripts import RuleStatusClassifier

classifier = RuleStatusClassifier()
status = classifier.classify(legata_path: str) -> dict
```

**Returns:**
```python
{
    "status": str,  # formalized | incomplete | incorrect | not-formalized | todo-placeholder
    "reason": str,
    "confidence": float
}
```

**Example:**
```python
classifier = RuleStatusClassifier()
status = classifier.classify("legata/Rule-22-Equipment-Range.legata")

if status["status"] == "formalized":
    print("Rule is ready for transformation")
elif status["status"] == "incomplete":
    print("Rule needs repair:", status["reason"])
```

### COLREGFallbackMapper

Map incomplete rules to COLREG text.

```python
from scripts import COLREGFallbackMapper

mapper = COLREGFallbackMapper()
mapping = mapper.map(rule_id: str) -> dict
```

**Returns:**
```python
{
    "rule_id": str,
    "colreg_text": str,
    "provisional_property": str,
    "confidence": float
}
```

**Example:**
```python
mapper = COLREGFallbackMapper()
mapping = mapper.map("Rule-23")

print("COLREG text:", mapping["colreg_text"])
print("Provisional property:", mapping["provisional_property"])
```

## Scoring Functions

### score_single_rule

Apply 100-point scoring rubric to a single rule.

```python
from scripts.score_single_rule import RubricScorer

scorer = RubricScorer()
scorecard = scorer.score_rule(
    rule_id: str,
    verify_status: str,
    is_vacuous: bool | None = None,
    assertion_id: str | None = None,
    rmc_exit_code: int | None = None,
    model_outcome: str | None = None,
    mutation_score: float | None = None,
    vacuity_comparison: str | None = None
) -> dict
```

**Parameters:**
- `rule_id` - Rule identifier
- `verify_status` - Verification status (pass/fail/timeout/blocked/unknown)
- `is_vacuous` - Vacuity result from vacuity checker (`True`/`False`/`None`)
- `assertion_id` - Assertion label used for vacuity audit trail
- `rmc_exit_code` - Baseline RMC exit code
- `model_outcome` - Runtime semantic outcome (`satisfied`/`cex`/`unknown`)
- `mutation_score` - Mutation score in `[0, 100]`
- `vacuity_comparison` - Semantic relation (`same`/`changed`/`unknown`)

**Returns:**
```python
{
    "rule_id": str,
    "score_total": int,  # 0-100
    "score_breakdown": {
        "syntax": int,              # 0-10
        "semantic_alignment": int,  # 0-55
        "verification_outcome": int,# 0-25
        "integrity": int            # 0-10
    },
    "mutation_score": float,
    "vacuity": {"passed": bool},
    "is_hallucination": bool,
    "status": str
}
```

**Example:**
```python
scorer = RubricScorer()
score = scorer.score_rule(
    rule_id="Rule-22",
    verify_status="pass",
    mutation_score=90.0,
    vacuity_comparison="same",
    model_outcome="satisfied",
    rmc_exit_code=0,
)

print(f"Score: {score['score_total']}/100")
```

## Reporting Functions

### generate_report

Generate aggregate reports from scorecards.

```python
from scripts import generate_report

generate_report(
    input_scores: str,
    output_dir: str,
    format: str = "both"  # json | markdown | both
) -> dict
```

**Parameters:**
- `input_scores` - Path to scorecards JSON file
- `output_dir` - Output directory for reports
- `format` - Report format (json/markdown/both)

**Returns:**
```python
{
    "json_path": str | None,
    "markdown_path": str | None,
    "summary": {
        "total_rules": int,
        "passed": int,
        "failed": int,
        "average_score": float
    }
}
```

**Example:**
```python
report = generate_report(
    input_scores="output/scorecards.json",
    output_dir="output/reports",
    format="both"
)

print(f"Total rules: {report['summary']['total_rules']}")
print(f"Average score: {report['summary']['average_score']}")
```

## Installation Functions

### install_artifacts

Install agents and skills to target directory.

```python
from scripts import install_artifacts

install_artifacts(
    target_root: str,
    mode: str = "all"  # all | agents | skills
) -> bool
```

**Parameters:**
- `target_root` - Installation target (e.g., `~/.agents`)
- `mode` - What to install (all/agents/skills)

**Returns:**
- `True` if successful, `False` otherwise

**Example:**
```python
success = install_artifacts(
    target_root="~/.agents",
    mode="all"
)
```

### verify_installation

Verify installed artifacts.

```python
from scripts import verify_installation

verify_installation(
    target_root: str,
    rmc_jar: str | None = None
) -> dict
```

**Parameters:**
- `target_root` - Installation root (e.g., `~/.agents`)
- `rmc_jar` - Path to RMC JAR (optional)

**Returns:**
```python
{
    "agents_ok": bool,
    "skills_ok": bool,
    "rmc_ok": bool,
    "errors": list[str]
}
```

**Example:**
```python
result = verify_installation(
    target_root="~/.agents",
    rmc_jar="~/.agents/rmc/rmc.jar"
)

if all([result["agents_ok"], result["skills_ok"], result["rmc_ok"]]):
    print("Installation verified")
```

## CLI Usage

All modules provide CLI interfaces:

```bash
# Download RMC
python3 -m scripts.download_rmc --url <url> --dest-dir <dir>

# Run verification
python3 -m scripts.run_rmc --jar <jar> --model <model> --property <property> --output-dir <dir>

# Classify rule
python3 -m scripts.classify_rule_status --legata-path <path> --output-json

# Score rule
python3 -m scripts.score_single_rule --rule-id <id> --verify-status <status> --output-json

# Generate report
python3 -m scripts.generate_report --input-scores <json> --output-dir <dir> --format both

# Setup
python3 setup.py
```

## Exit Codes

### run_rmc
- `0` - Success (parse + compile)
- `3` - Timeout
- `4` - C++ compilation failed
- `5` - Rebeca parse failed

### setup.py
- `0` - Success
- `1` - Prerequisites missing
- `2` - RMC download failed
- `3` - RMC verification failed
- `4` - Artifact installation failed

**Note:** The legacy `setup_agent.py` has been removed. Use the root-level `setup.py` instead.

## Root Setup Script

The repository includes a root-level `setup.py` that auto-discovers and installs all agents and skills:

```bash
python3 setup.py
```

This script:
- Discovers all agents in `agents/` directory
- Discovers all skills in `skills/` directory (directories with SKILL.md)
- Downloads and verifies RMC
- Installs everything to `~/.agents/`

Exit codes:
- `0` - Success
- `1` - Prerequisites missing
- `2` - RMC download failed
- `3` - RMC verification failed
- `4` - Artifact installation failed

## Next Steps

- [Usage Guide](usage.md) - Complete workflow examples
- [Architecture Guide](architecture.md) - System design
