# API Reference

Complete Python library reference for `skills/rebeca-tooling/lib/`.

## Installation

```python
import sys
from pathlib import Path

# Add rebeca-tooling skill to path
tooling_skill = Path("~/.claude/skills/rebeca-tooling").expanduser()
sys.path.insert(0, str(tooling_skill))

from lib import *
```

## Core Functions

### download_rmc

Download RMC from GitHub releases.

```python
from lib import download_rmc

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
    dest_dir="~/.claude/rmc"
)
```

### run_rmc

Execute RMC model checker with C++ compilation.

```python
from lib import run_rmc

run_rmc(
    jar: str,
    model: str,
    property_file: str,
    output_dir: str,
    timeout_seconds: int = 120
) -> dict
```

**Parameters:**
- `jar` - Path to RMC JAR file
- `model` - Path to `.rebeca` model file
- `property_file` - Path to `.property` file
- `output_dir` - Output directory for verification artifacts
- `timeout_seconds` - Timeout in seconds (default: 120)

**Returns:**
```python
{
    "exit_code": int,  # 0=success, 3=timeout, 4=compile failed, 5=parse failed
    "stdout": str,
    "stderr": str,
    "output_dir": str
}
```

**Example:**
```python
result = run_rmc(
    jar="~/.claude/rmc/rmc.jar",
    model="output/Rule-22.rebeca",
    property_file="output/Rule-22.property",
    output_dir="output/verification",
    timeout_seconds=120
)

if result["exit_code"] == 0:
    print("Verification successful")
elif result["exit_code"] == 5:
    print("Parse error:", result["stderr"])
```

### pre_run_rmc_check

Auto-provision RMC before execution.

```python
from lib import pre_run_rmc_check

pre_run_rmc_check(
    rmc_dir: str | None = None,
    download_if_missing: bool = True
) -> bool
```

**Parameters:**
- `rmc_dir` - RMC directory (default: `~/.claude/rmc`)
- `download_if_missing` - Auto-download if not found

**Returns:**
- `True` if RMC available, `False` otherwise

**Example:**
```python
if pre_run_rmc_check():
    result = run_rmc(...)
```

### setup_agent

Unified setup script for prerequisites, RMC, and installation.

```python
from lib import setup_agent

setup_agent(
    rmc_url: str | None = None,
    rmc_dir: str | None = None,
    target_root: str | None = None,
    skip_prereq_check: bool = False
) -> int
```

**Parameters:**
- `rmc_url` - RMC download URL (default: latest release)
- `rmc_dir` - RMC installation directory (default: `~/.claude/rmc`)
- `target_root` - Installation target (default: `~/.claude`)
- `skip_prereq_check` - Skip prerequisite checks

**Returns:**
- `0` - Success
- `1` - Prerequisites missing
- `2` - RMC download failed
- `3` - RMC verification failed
- `4` - Artifact installation failed

**Example:**
```bash
python3 ~/.claude/skills/rebeca-tooling/lib/setup_agent.py
```

## Classification Functions

### RuleStatusClassifier

Classify Legata rule formalization status.

```python
from lib import RuleStatusClassifier

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
from lib import COLREGFallbackMapper

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
from lib import score_single_rule

score_single_rule(
    rule_id: str,
    verify_status: str,
    syntax_correct: bool = True,
    semantic_aligned: bool = True
) -> dict
```

**Parameters:**
- `rule_id` - Rule identifier
- `verify_status` - Verification status (pass/fail/timeout/error)
- `syntax_correct` - Whether syntax is correct
- `semantic_aligned` - Whether semantics are aligned

**Returns:**
```python
{
    "rule_id": str,
    "total_score": int,  # 0-100
    "breakdown": {
        "syntax": int,      # 0-40
        "semantics": int,   # 0-30
        "verification": int # 0-30
    },
    "status": str
}
```

**Example:**
```python
score = score_single_rule(
    rule_id="Rule-22",
    verify_status="pass",
    syntax_correct=True,
    semantic_aligned=True
)

print(f"Score: {score['total_score']}/100")
```

## Reporting Functions

### generate_report

Generate aggregate reports from scorecards.

```python
from lib import generate_report

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
from lib import install_artifacts

install_artifacts(
    target_root: str,
    mode: str = "all"  # all | agents | skills
) -> bool
```

**Parameters:**
- `target_root` - Installation target (e.g., `~/.claude`)
- `mode` - What to install (all/agents/skills)

**Returns:**
- `True` if successful, `False` otherwise

**Example:**
```python
success = install_artifacts(
    target_root="~/.claude",
    mode="all"
)
```

### verify_installation

Verify installed artifacts.

```python
from lib import verify_installation

verify_installation(
    target_root: str,
    rmc_jar: str | None = None
) -> dict
```

**Parameters:**
- `target_root` - Installation root (e.g., `~/.claude`)
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
    target_root="~/.claude",
    rmc_jar="~/.claude/rmc/rmc.jar"
)

if all([result["agents_ok"], result["skills_ok"], result["rmc_ok"]]):
    print("Installation verified")
```

## CLI Usage

All modules provide CLI interfaces:

```bash
# Download RMC
python3 -m lib.download_rmc --url <url> --dest-dir <dir>

# Run verification
python3 -m lib.run_rmc --jar <jar> --model <model> --property <property> --output-dir <dir>

# Classify rule
python3 -m lib.classify_rule_status --legata-path <path> --output-json

# Score rule
python3 -m lib.score_single_rule --rule-id <id> --verify-status <status> --output-json

# Generate report
python3 -m lib.generate_report --input-scores <json> --output-dir <dir> --format both

# Setup
python3 -m lib.setup_agent
```

## Exit Codes

### run_rmc
- `0` - Success (parse + compile)
- `3` - Timeout
- `4` - C++ compilation failed
- `5` - Rebeca parse failed

### setup_agent
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
- Installs everything to `~/.claude/`

Exit codes:
- `0` - Success
- `1` - Prerequisites missing
- `2` - RMC download failed
- `3` - RMC verification failed
- `4` - Artifact installation failed

## Next Steps

- [Usage Guide](usage.md) - Complete workflow examples
- [Architecture Guide](architecture.md) - System design
