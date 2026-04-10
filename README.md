# Claude Rebeca

A collection of Claude Code agents and skills for actor-based formal verification and model checking workflows, with a focus on transforming formal specifications into verifiable models.

## Overview

This repository provides reusable agents and skills for:
- **Formal specification transformation** - Convert Legata/COLREG rules to Rebeca actor models
- **Model checking automation** - Execute RMC (Rebeca Model Checker) with verification workflows
- **Rule triage and classification** - Assess formalization quality and suggest repairs
- **Scoring and reporting** - Generate comprehensive verification reports

## Quick Links

- **[Installation Guide](docs/guides/installation.md)** - Setup instructions for all platforms
- **[Usage Guide](docs/guides/usage.md)** - Workflow execution examples
- **[Architecture](docs/guides/architecture.md)** - System design and components

### Agents
- **[legata-to-rebeca](docs/agents/legata-to-rebeca.md)** - Transform Legata/COLREG rules to Rebeca models

### Skills
- **[legata-to-rebeca](docs/skills/legata-to-rebeca.md)** - Workflow guidance
- **[rebeca-handbook](docs/skills/rebeca-handbook.md)** - Modeling best practices
- **[rebeca-tooling](docs/skills/rebeca-tooling.md)** - Python library and CLI tools

## Quick Start

```bash
# One-command setup
python3 setup.py

# Transform a rule
@legata-to-rebeca Transform legata/Rule-22-Equipment-Range.legata to Rebeca.
Reference model: src/PromptingExperimentDoc/SimulationModelCode.rebeca
Reference property: src/PromptingExperimentDoc/SimulationModelCode.property
```

The `setup.py` script automatically:
- Discovers all agents in `agents/` directory
- Discovers all skills in `skills/` directory
- Downloads and verifies RMC model checker
- Installs everything to `~/.claude/`

## Requirements

- **Python 3.8+** (cross-platform)
- **Java 11+** (for RMC model checker)
- **C++ compiler** (g++/clang for RMC compilation)

**Platform Support:** ✅ Windows | ✅ macOS | ✅ Linux

See [Installation Guide](docs/guides/installation.md) for platform-specific instructions.

## Documentation

### Guides
- [Installation](docs/guides/installation.md) - Setup and prerequisites
- [Usage](docs/guides/usage.md) - Workflow execution
- [Architecture](docs/guides/architecture.md) - System design
- [API Reference](docs/guides/api-reference.md) - Python library reference
- [Troubleshooting](docs/guides/troubleshooting.md) - Common issues

### Agents
- [legata-to-rebeca](docs/agents/legata-to-rebeca.md) - Legata→Rebeca transformation agent

### Skills
- [legata-to-rebeca](docs/skills/legata-to-rebeca.md) - Workflow guidance skill
- [rebeca-handbook](docs/skills/rebeca-handbook.md) - Modeling best practices skill
- [rebeca-tooling](docs/skills/rebeca-tooling.md) - Python tooling skill

## Directory Structure

```
claude-rebeca/
├── agents/                      # Claude Code agents
├── skills/                      # Reusable skills
│   └── rebeca-tooling/lib/     # Python library (10 modules)
├── configs/                     # Experiment configurations
├── tests/                       # Acceptance and functional tests
├── docs/                        # Documentation
│   ├── agents/                 # Per-agent documentation
│   ├── skills/                 # Per-skill documentation
│   └── guides/                 # Installation, usage, architecture
└── examples/                    # Example transformations
```

## Contributing

See [Contributing Guide](docs/guides/contributing.md) for details on adding agents, skills, or tooling.