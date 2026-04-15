---
name: rebeca_tooling
version: 1.0.0
description: Cross-platform Python library for RMC operations, rule triage, scoring, and reporting
trigger_phrases:
  - "download rmc"
  - "run rmc"
  - "verify rebeca"
  - "score rule"
  - "triage rule"
  - "generate report"
---

# Rebeca Tooling Skill

## Purpose

This skill provides a cross-platform Python library for all Rebeca model checking operations, including:
- RMC download and execution
- Rule status classification and triage
- COLREG fallback mapping
- Single-rule scoring and aggregate reporting
- Installation and verification utilities

## When to Use

Use this skill when you need to:
- Download or execute the RMC model checker
- Classify Legata rule formalization status
- Generate provisional properties from COLREG text
- Score verification results
- Generate aggregate reports
- Install or verify toolchain artifacts

## Library Location

All Python modules are in `scripts/` subdirectory of this skill:
```
skills/rebeca_tooling/
├── SKILL.md (this file)
└── scripts/
    ├── __init__.py
    ├── utils.py
    ├── download_rmc.py
    ├── run_rmc.py
    ├── pre_run_rmc_check.py
    ├── install_artifacts.py
    ├── verify_installation.py
    ├── classify_rule_status.py
    ├── colreg_fallback_mapper.py
    ├── score_single_rule.py
    └── generate_report.py
```

## Python Library Usage

### Import from Skill

```python
import sys
from pathlib import Path

# Add skill's lib to path
skill_path = Path("~/.agents/skills/rebeca_tooling").expanduser()
sys.path.insert(0, str(skill_path))

from scripts import (
    download_rmc,
    run_rmc,
    pre_run_rmc_check,
    RuleStatusClassifier,
    COLREGFallbackMapper
)
```

### RMC Operations

#### Download RMC

```python
from scripts import download_rmc

# Download latest release
result = download_rmc(
    url="https://github.com/rebeca-lang/org.rebecalang.rmc/releases/latest",
    dest_dir=".agents/rmc"
)

# Download specific version
result = download_rmc(
    url="https://github.com/rebeca-lang/org.rebecalang.rmc/releases",
    dest_dir=".agents/rmc",
    tag="2.14"
)

# Exit codes:
# 0: Success
# 1: Checksum mismatch
# 2: Download failed
```

#### Run RMC Verification

```python
from scripts import run_rmc

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
# 1: Invalid inputs
# 3: Timeout
# 4: C++ compilation failed
# 5: Rebeca parse failed
```

#### Auto-Provision RMC

```python
from scripts import pre_run_rmc_check

# Ensures RMC is available, downloads if needed.
# Resolves jar path from: RMC_DESTINATION env var → .agents/rmc_path marker → ~/.agents/rmc
result = pre_run_rmc_check()

# Exit codes:
# 0: RMC available
# 2: Download failed
```

### Rule Triage

#### Classify Rule Status

```python
from scripts import RuleStatusClassifier

classifier = RuleStatusClassifier()
result = classifier.classify("path/to/rule.legata")

# Returns dict with:
# - status: formalized|incomplete|incorrect|not-formalized|todo-placeholder
# - clause_count: number of clauses
# - evidence: list of findings
# - defects: list of defects
# - next_action: recommended action
```

#### COLREG Fallback Mapping

```python
from scripts import COLREGFallbackMapper

mapper = COLREGFallbackMapper()
result = mapper.map_rule(
    rule_id="Rule-99",
    colreg_text="Every vessel shall maintain a proper lookout"
)

# Returns dict with:
# - provisional_property: Rebeca property text
# - confidence: high|medium|low
# - assumptions: list of assumptions
# - requires_manual_review: bool
# - mapping_path: "colreg-fallback"
```

### Scoring and Reporting

#### Score Single Rule

```python
from scripts.score_single_rule import RubricScorer

scorer = RubricScorer()
scorecard = scorer.score_rule(
    rule_id="Rule-22",
    verify_status="pass",  # pass|fail|timeout|blocked|unknown
    model_artifact="model.rebeca",
    property_artifact="property.property"
)

# Returns dict with:
# - score_total: 0-100
# - score_breakdown: {syntax:10, semantic_alignment:55, verification_outcome:25, hallucination_penalty:10}
# - status: Pass|Fail|Conditional|Blocked|Unknown
# - confidence: 0.0-1.0
# - mapping_path: legata|colreg-fallback
# - failure_reasons: list
# - remediation_hints: list
```

#### Generate Aggregate Report

```python
from scripts.generate_report import ReportGenerator

generator = ReportGenerator()
generator.add_scorecard(scorecard)
generator.finalize()

Path("reports/").mkdir(parents=True, exist_ok=True)
with open("reports/report.json", "w") as f:
    f.write(generator.to_json())
with open("reports/report.md", "w") as f:
    f.write(generator.to_markdown())

# Outputs: reports/report.json and reports/report.md
```

### Installation Utilities

#### Install Artifacts

```python
from scripts import install_artifacts

result = install_artifacts(
    target_root=".claude",
    mode="all"  # agent|skill|all
)

# Exit codes:
# 0: Success
# 1: Installation failed
```

#### Verify Installation

```python
from scripts import verify_installation

result = verify_installation(target_root=".claude")

# Exit codes:
# 0: All artifacts present
# 1: Missing artifacts
```

#### Complete Setup

Use `setup.py` at the repo root instead — it handles prerequisites, RMC download, artifact installation, and path patching in one step:

```bash
# Local install (.agents/ in CWD)
python3 setup.py

# Global install (~/.agents/)
python3 setup.py --mode global
```

## CLI Usage

All modules have command-line interfaces:

### RMC Operations

```bash
# Download RMC
python3 ~/.agents/skills/rebeca_tooling/scripts/download_rmc.py \
  --url https://github.com/rebeca-lang/org.rebecalang.rmc/releases/latest \
  --dest-dir .agents/rmc

# Run verification
python3 ~/.agents/skills/rebeca_tooling/scripts/run_rmc.py \
  --jar .agents/rmc/rmc.jar \
  --model model.rebeca \
  --property property.property \
  --output-dir output \
  --timeout-seconds 120 \
  --jvm-opt "-Xmx2g"

# Pre-run check
python3 ~/.agents/skills/rebeca_tooling/scripts/pre_run_rmc_check.py
```

### Rule Triage

```bash
# Classify rule status
python3 ~/.agents/skills/rebeca_tooling/scripts/classify_rule_status.py \
  --legata-path legata/Rule-22.legata \
  --output-json

# COLREG fallback mapping
python3 ~/.agents/skills/rebeca_tooling/scripts/colreg_fallback_mapper.py \
  --rule-id Rule-99 \
  --colreg-text "Every vessel shall maintain a proper lookout" \
  --output-json
```

### Scoring and Reporting

```bash
# Score single rule
python3 ~/.agents/skills/rebeca_tooling/scripts/score_single_rule.py \
  --rule-id Rule-22 \
  --verify-status pass \
  --output-json

# Generate report
python3 ~/.agents/skills/rebeca_tooling/scripts/generate_report.py \
  --input-scores results.json \
  --output-dir reports/ \
  --format both
```

### Installation

```bash
# Complete setup (use setup.py instead — see above)

# Install artifacts only
python3 ~/.agents/skills/rebeca_tooling/scripts/install_artifacts.py \
  --target-root .claude \
  --mode all

# Verify installation
python3 ~/.agents/skills/rebeca_tooling/scripts/verify_installation.py .claude
```

## Platform Support

All modules work identically on:
- **Windows** (Python 3.8+ with g++/MinGW or WSL2)
- **macOS** (Python 3.8+ with Xcode Command Line Tools)
- **Linux** (Python 3.8+ with build-essential)

## Prerequisites

- Python 3.8+
- Java 11+ (for RMC)
- C++ compiler (g++ or clang, for RMC C++ compilation)

## Error Handling Pattern

```python
from scripts import run_rmc

def verify_rule(rule_id: str, model_path: str, property_path: str) -> dict:
    """Verify a single rule and return structured result."""
    output_dir = f"verification_output/{rule_id}"

    result = run_rmc(
        jar=".agents/rmc/rmc.jar",
        model=model_path,
        property_file=property_path,
        output_dir=output_dir,
        timeout_seconds=120
    )

    if result == 0:
        return {"rule_id": rule_id, "status": "verified"}
    elif result == 5:
        return {"rule_id": rule_id, "status": "syntax_error", "error_type": "rebeca_parse"}
    elif result == 4:
        return {"rule_id": rule_id, "status": "syntax_error", "error_type": "cpp_compile"}
    elif result == 3:
        return {"rule_id": rule_id, "status": "timeout"}
    else:
        return {"rule_id": rule_id, "status": "error", "exit_code": result}
```

## Integration with Other Skills

Other skills can reference this tooling skill:

```python
# In another skill or agent
import sys
from pathlib import Path

# Reference rebeca_tooling skill
tooling_skill = Path("~/.agents/skills/rebeca_tooling").expanduser()
sys.path.insert(0, str(tooling_skill))

from scripts import run_rmc, RuleStatusClassifier

# Use tooling functions
classifier = RuleStatusClassifier()
status = classifier.classify("rule.legata")

if status["status"] == "formalized":
    result = run_rmc(...)
```

## Module Reference

| Module | Purpose | CLI | Library | Exported |
|--------|---------|-----|---------|----------|
| `utils.py` | `safe_path`, `safe_open`, `validate_https_url`, `resolve_executable` — shared security guards | ✗ | ✓ | ✓ |
| `download_rmc.py` | Download RMC from GitHub | ✓ | ✓ | ✓ |
| `run_rmc.py` | Execute RMC model checker | ✓ | ✓ | ✓ |
| `pre_run_rmc_check.py` | Auto-provision RMC | ✓ | ✓ | ✓ |
| `install_artifacts.py` | Install agent/skills | ✓ | ✓ | ✓ |
| `verify_installation.py` | Verify installation | ✓ | ✓ | ✓ |
| `classify_rule_status.py` | Rule status classification | ✓ | ✓ | ✓ |
| `colreg_fallback_mapper.py` | COLREG fallback mapping | ✓ | ✓ | ✓ |
| `score_single_rule.py` | 100-point scoring rubric | ✓ | ✓ | ✗ (use directly) |
| `generate_report.py` | Aggregate reporting | ✓ | ✓ | ✗ (use directly) |

## Best Practices

1. **Always use pre_run_rmc_check()** before calling run_rmc() to ensure RMC is available
2. **Check exit codes** - Don't assume success, handle all error cases
3. **Use absolute paths** - Avoid relative paths for jar, model, and property files
4. **Set appropriate timeouts** - Complex models may need >120s
5. **Handle C++ compilation failures** - Exit code 4 means g++ failed, not RMC
6. **Distinguish parse vs compile errors** - Exit code 5 (parse) vs 4 (compile)
7. **Review fallback mappings** - COLREG fallback always requires manual review

## Troubleshooting

### Import Errors

If you get `ModuleNotFoundError`:
```python
# Ensure skill path is correct
skill_path = Path("~/.agents/skills/rebeca_tooling").expanduser()
print(f"Skill path exists: {skill_path.exists()}")
print(f"Scripts path exists: {(skill_path / 'scripts').exists()}")
```

### RMC Not Found

```python
from scripts import pre_run_rmc_check

# This will auto-download if missing
result = pre_run_rmc_check()
if result != 0:
    print("Failed to provision RMC")
```

### C++ Compilation Failures

Exit code 4 means g++ failed. Check:
```bash
g++ --version  # Ensure g++ is installed
```

Install if missing:
- Ubuntu/Debian: `sudo apt install build-essential`
- macOS: `xcode-select --install`
- Windows: Install MinGW or use WSL2

## See Also

- **legata_to_rebeca** skill - Workflow guidance
- **rebeca-handbook** skill - Modeling best practices
- **legata_to_rebeca** agent - Main orchestration agent
