# Architecture Guide

System design and component overview for RebecAI.

## Overview

RebecAI follows a modular architecture with three main layers:

1. **Agent Layer** - Claude Code agents orchestrating workflows
2. **Skills Layer** - Reusable knowledge and tooling
3. **Tooling Layer** - Cross-platform Python library

## Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Agent Layer                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │         legata-to-rebeca Agent                    │  │
│  │  - Orchestrates 8-phase workflow                  │  │
│  │  - Invokes skills for guidance                    │  │
│  │  - Calls tooling for automation                   │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    Skills Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ legata-to-   │  │   rebeca-    │  │   rebeca-    │   │
│  │   rebeca     │  │  handbook    │  │   tooling    │   │
│  │              │  │              │  │              │   │
│  │ Workflow     │  │ Modeling     │  │ Python       │   │
│  │ guidance     │  │ best         │  │ library      │   │
│  │              │  │ practices    │  │              │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   Tooling Layer                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │       skills/rebeca-tooling/scripts/              │  │
│  │  - utils.py              (security guards)        │  │
│  │  - download_rmc.py                                │  │
│  │  - run_rmc.py                                     │  │
│  │  - pre_run_rmc_check.py                           │  │
│  │  - classify_rule_status.py                        │  │
│  │  - colreg_fallback_mapper.py                      │  │
│  │  - score_single_rule.py                           │  │
│  │  - generate_report.py                             │  │
│  │  - install_artifacts.py                           │  │
│  │  - verify_installation.py                         │  │
│  │  - __init__.py                                    │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  Root Utilities (project root, not installed):          │
│  - setup.py     (one-command install)                   │
│  - purge.py     (surgical cleanup of installed files)   │
└─────────────────────────────────────────────────────────┘
```

## Design Principles

### 1. Modularity
- **Agents** orchestrate workflows but don't implement logic
- **Skills** provide reusable knowledge and patterns
- **Tooling** implements cross-platform automation

### 2. Separation of Concerns
- **Workflow logic** - In agent definitions
- **Domain knowledge** - In skills
- **Automation** - In Python library

### 3. Cross-Platform Support
- All tooling written in Python 3.8+
- Platform-specific logic abstracted
- Supports Windows, macOS, Linux

### 4. Claude Code Compliance
- Follows `~/.agents/agents/` and `~/.agents/skills/` conventions
- Tooling embedded in `skills/rebeca-tooling/scripts/`
- Root `setup.py` and `purge.py` are project-level utilities, not installed artifacts

## Workflow Execution

### Phase 1: Agent Invocation
```
User → @legata-to-rebeca → Agent reads definition
```

### Phase 2: Skill Consultation
```
Agent → legata-to-rebeca skill → Workflow guidance
Agent → rebeca-handbook skill → Modeling patterns
```

### Phase 3: Tooling Execution
```
Agent → rebeca-tooling skill → Python library
Python library → RMC → Verification result
```

### Phase 4: Result Processing
```
Python library → Scoring → Report generation
Agent → User → Results and recommendations
```

## Data Flow

### Input
1. **Legata rule file** - Formal specification
2. **Reference model** - Base `.rebeca` file
3. **Reference property** - Base `.property` file

### Processing
1. **Triage** - Classify rule status
2. **Transform** - Generate Rebeca model and property
3. **Verify** - Run RMC model checker
4. **Score** - Apply 100-point rubric
5. **Report** - Generate JSON and Markdown

### Output
1. **Model files** - `.rebeca` and `.property`
2. **Verification logs** - RMC stdout/stderr
3. **Scorecards** - JSON scoring results
4. **Reports** - Aggregate summaries

## RMC Workflow

### Critical Phases

1. **Parse** - RMC parses `.rebeca` and `.property`
   - Exit code 5 if syntax error

2. **Generate** - RMC generates C++ source files
   - Uses `-x` flag for C++ generation

3. **Compile** - g++ compiles C++ to executable
   - Exit code 4 if compilation fails

4. **Execute** - Run executable for verification
   - Counterexample if property violated

### Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | Property verified |
| 3 | Timeout | Increase timeout or simplify model |
| 4 | Compile failed | Check RMC version or model complexity |
| 5 | Parse failed | Fix syntax errors in model/property |

## Directory Structure

```
# Repository (source of truth)
rebecai/
├── agents/
│   └── legata-to-rebeca.md          # Agent definition
├── skills/
│   ├── legata-to-rebeca/
│   │   └── SKILL.md                 # Workflow guidance
│   ├── rebeca-handbook/
│   │   └── SKILL.md                 # Modeling best practices
│   └── rebeca-tooling/
│       ├── SKILL.md                 # Tooling documentation
│       └── scripts/                 # Python library (10 modules)
├── docs/                            # Developer documentation
├── setup.py                         # One-command installer
└── purge.py                         # Surgical cleanup utility

# Installed (after running setup.py)
~/.agents/
├── agents/
│   └── legata-to-rebeca.md
├── skills/
│   ├── legata-to-rebeca/
│   ├── rebeca-handbook/
│   └── rebeca-tooling/
│       └── scripts/                 # Python library (10 modules)
└── rmc/
    └── rmc.jar                      # RMC model checker
```

## Installed Paths

After running `python3 setup.py` from the project root, artifacts are placed at:

| Artifact | Installed Path |
|----------|---------------|
| Agent definition | `~/.agents/agents/legata-to-rebeca.md` |
| Workflow guidance skill | `~/.agents/skills/legata-to-rebeca/SKILL.md` |
| Modeling handbook skill | `~/.agents/skills/rebeca-handbook/SKILL.md` |
| Tooling skill + scripts | `~/.agents/skills/rebeca-tooling/scripts/` |
| RMC model checker | `~/.agents/rmc/rmc.jar` |

To clean up all installed artifacts before a re-install: `python3 purge.py && python3 setup.py`

## Extension Points

### Adding New Agents

1. Create agent definition in `agents/`
2. Reference existing skills
3. Document in `docs/agents/`
4. Add usage examples

### Adding New Skills

1. Create skill directory in `skills/`
2. Add `SKILL.md` with knowledge/patterns
3. Document in `docs/skills/`
4. Update agent references

### Adding New Tooling

1. Create module in `skills/rebeca-tooling/lib/`
2. Add CLI interface with argparse
3. Export from `__init__.py`
4. Update skill documentation
5. Add tests

## Testing Strategy

### Acceptance Tests
- End-to-end workflow validation
- Real Legata rules → Rebeca models
- RMC verification execution

### Functional Tests
- Per-module unit tests
- Mock RMC execution
- Edge case handling

### Leakage Scan
- Detect hardcoded paths
- Ensure cross-platform compatibility
- Validate configuration handling

## Performance Considerations

### RMC Execution
- Default timeout: 120 seconds
- Configurable per-rule
- Parallel execution for batch processing

### C++ Compilation
- Uses `-w` flag to suppress warnings
- Compilation typically < 5 seconds
- Failure indicates RMC code generation issue

### Scoring and Reporting
- Lightweight JSON processing
- Markdown generation from templates
- Minimal overhead

## Security Considerations

### Input Validation
- Validate file paths before execution
- Sanitize user-provided rule IDs
- Check file permissions

### Subprocess Execution
- Use subprocess.run with timeout
- Capture stdout/stderr separately
- Handle exit codes explicitly

### Credential Management
- No credentials stored in code
- No network calls except RMC download
- Local-only execution

## Next Steps

- [API Reference](api-reference.md) - Complete function signatures
- [Contributing Guide](contributing.md) - How to extend the system
