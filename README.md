# RebecaAI

A centralized ecosystem for AI-agents and skills designed for actor-based formal verification using the Rebeca Model Checker (RMC).

## Overview

RebecaAI provides a unified framework to:
- **Transform** formal specifications (Legata/COLREG) into verifiable Rebeca actor models.
- **Automate** model checking workflows using RMC.
- **Triage** rules for formalization quality.
- **Report** verification outcomes through automated tooling.

## Repository Structure

Understanding the organization is key to extending the framework. We maintain a strict separation between implementation code and supporting documentation.

| Category | Implementation Path | Documentation Path | Purpose |
| :--- | :--- | :--- | :--- |
| **Agents** | `agents/` | `docs/agents/` | Autonomous agents for specific workflows. |
| **Skills** | `skills/` | `docs/skills/` | Reusable skills for model checking and analysis. |
| **Guides** | N/A | `docs/guides/` | Procedural workflows, setup, and architecture. |

*   **Implementation (`/agents`, `/skills`)**: Contains the executable code, scripts, and configuration that define agent behaviors and tool capabilities.
*   **Documentation (`/docs`)**: Contains the developer-facing technical manuals, usage guides, and skill specifications.

## Quick Links

- **[Installation Guide](docs/guides/installation.md)** - Setup instructions for all platforms
- **[Usage Guide](docs/guides/usage.md)** - Workflow execution examples
- **[Architecture](docs/guides/architecture.md)** - System design and components

## Agents & Skills Overview

Currently, the following components are implemented and available for use:

### Active Agents
| Agent | Description | Implementation Path |
| :--- | :--- | :--- |
| `legata_to_rebeca` | Transforms Legata/COLREG specifications into Rebeca models. | `agents/legata_to_rebeca.md` |

### Active Skills
| Skill | Description | Implementation Path |
| :--- | :--- | :--- |
| `legata_to_rebeca` | Workflow guidance and pattern application. | `skills/legata_to_rebeca/` |
| `rebeca_handbook` | Best practices for actor-based modeling. | `skills/rebeca_handbook/` |
| `rebeca_tooling` | Python library/CLI for RMC execution and reporting. | `skills/rebeca_tooling/` |

# Quick Start

```bash
# One-command setup
python3 setup.py

# Clean up installed artifacts
python3 purge.py

# Example: Transform a rule using an agent
@legata_to_rebeca Transform legata/Rule-22-Equipment-Range.legata to Rebeca.
```

The `setup.py` script automatically discovers components in `agents/` and `skills/`, downloads RMC, and installs them to `~/.agents/`.

## Requirements

- **Python 3.8+** | **Java 11+** (for RMC) | **C++ compiler** (g++/clang)
- **Platforms:** ✅ macOS, ✅ Linux, ✅ Windows

## Contributing

See [Contributing Guide](docs/guides/contributing.md) to learn how to add new agents or improve existing skills.