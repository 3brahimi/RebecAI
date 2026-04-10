# rebeca-tooling Skill

Cross-platform Python library providing automation for RMC model checking, rule classification, scoring, and reporting.

## Purpose

This skill provides:
- **RMC automation** - Download, execute, and manage RMC
- **Rule classification** - Triage Legata formalization status
- **COLREG fallback** - Map incomplete rules to COLREG text
- **Scoring** - Apply 100-point rubric
- **Reporting** - Generate JSON and Markdown reports
- **Installation utilities** - Setup and verification

## Python Modules

The skill contains 10 Python modules in `skills/rebeca-tooling/lib/`:

| Module | Purpose | CLI | Library |
|--------|---------|-----|---------|
| `download_rmc.py` | Download RMC from GitHub | ✅ | ✅ |
| `run_rmc.py` | Execute RMC with C++ compilation | ✅ | ✅ |
| `pre_run_rmc_check.py` | Auto-provision RMC | ✅ | ✅ |
| `install_artifacts.py` | Install agents/skills | ✅ | ✅ |
| `verify_installation.py` | Verify installation | ✅ | ✅ |
| `classify_rule_status.py` | Rule status classification | ✅ | ✅ |
| `colreg_fallback_mapper.py` | COLREG fallback mapping | ✅ | ✅ |
| `score_single_rule.py` | Single rule scoring | ✅ | ✅ |
| `generate_report.py` | Aggregate reporting | ✅ | ✅ |
| `__init__.py` | Package exports | - | ✅ |

## Usage

### As Python Library

```python
import sys
from pathlib import Path

# Add rebeca-tooling skill to path
tooling_skill = Path("~/.claude/skills/rebeca-tooling").expanduser()
sys.path.insert(0, str(tooling_skill))

from lib import (
    download_rmc,
    run_rmc,
    RuleStatusClassifier,
    COLREGFallbackMapper
)

# Ensure RMC available
from lib import pre_run_rmc_check
pre_run_rmc_check()

# Run verification
result = run_rmc(
    jar="~/.claude/rmc/rmc.jar",
    model="model.rebeca",
    property_file="property.property",
    output_dir="output",
    timeout_seconds=120
)
```

### As CLI Tools

```bash
# Setup (use root setup.py instead)
python3 setup.py

# Download RMC
python3 ~/.claude/skills/rebeca-tooling/lib/download_rmc.py \
  --url https://github.com/rebeca-lang/org.rebecalang.rmc/releases/latest \
  --dest-dir ~/.claude/rmc

# Run verification
python3 ~/.claude/skills/rebeca-tooling/lib/run_rmc.py \
  --jar ~/.claude/rmc/rmc.jar \
  --model model.rebeca \
  --property property.property \
  --output-dir output \
  --timeout-seconds 120

# Classify rule
python3 ~/.claude/skills/rebeca-tooling/lib/classify_rule_status.py \
  --legata-path legata/Rule-22.legata \
  --output-json

# Score rule
python3 ~/.claude/skills/rebeca-tooling/lib/score_single_rule.py \
  --rule-id Rule-22 \
  --verify-status pass \
  --output-json

# Generate report
python3 ~/.claude/skills/rebeca-tooling/lib/generate_report.py \
  --input-scores results.json \
  --output-dir reports/ \
  --format both
```

## Exit Codes

### run_rmc
- `0`: Success (parse + compile)
- `3`: Timeout
- `4`: C++ compilation failed
- `5`: Rebeca parse failed

### setup_agent
- `0`: Success
- `1`: Prerequisites missing
- `2`: RMC download failed
- `3`: RMC verification failed
- `4`: Artifact installation failed

## Platform Support

✅ **Windows** (Python 3.8+ with g++/MinGW or WSL2)
✅ **macOS** (Python 3.8+ with Xcode Command Line Tools)
✅ **Linux** (Python 3.8+ with build-essential)

## API Reference

See [API Reference Guide](../guides/api-reference.md) for complete function signatures and examples.

## Related Skills

- **[legata-to-rebeca](legata-to-rebeca.md)** - Workflow guidance
- **[rebeca-handbook](rebeca-handbook.md)** - Modeling best practices

## Related Agents

- **[legata-to-rebeca](../agents/legata-to-rebeca.md)** - Uses this skill for automation
