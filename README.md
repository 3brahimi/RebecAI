# RebecAI

A multi-agent orchestration (MAO) system for transforming maritime safety rules from Legata formal specifications into verifiable Rebeca actor models, automated via the Rebeca Model Checker (RMC).

## Overview

RebecAI provides a unified framework to:
- **Transform** formal specifications (Legata/COLREG) into verifiable Rebeca actor models
- **Automate** model checking workflows using RMC across Step01–Step08
- **Triage** rules for formalization quality
- **Verify** properties using mutation scoring and vacuity checks
- **Report** verification outcomes through automated tooling

## Repository Structure

| Category | Implementation Path | Documentation Path | Purpose |
| :--- | :--- | :--- | :--- |
| **Agents** | `agents/` | `docs/agents/` | Coordinator + 8 specialist subagents |
| **Skills** | `skills/` | `docs/skills/` | Reusable knowledge injected at subagent startup |
| **Guides** | N/A | `docs/guides/` | Procedural workflows, setup, and architecture |

## Quick Start

```bash
# Clone and install
git clone https://github.com/3brahimi/RebecAI.git
cd RebecAI
python3 setup.py

# Preview what would be installed (no writes)
python3 setup.py --dry-run

# Remote install (no clone required)
curl -sSL https://raw.githubusercontent.com/3brahimi/RebecAI/main/setup.py | python3 -

# Clean up all installed artifacts before re-install
python3 purge.py && python3 setup.py

# Example: Transform a rule
@legata_to_rebeca Transform legata/Rule-22-Equipment-Range.legata to Rebeca.
Reference model: legata/rebeca/SimulationModelCode.rebeca
Reference property: legata/rebeca/SimulationModelCode.property
```

## Architecture: Multi-Agent Orchestration

`legata_to_rebeca` is a **coordinator** that delegates each pipeline step to a specialist subagent. Each specialist runs in its own context window, calls deterministic Python scripts via `Bash`, and emits a structured JSON contract back to the coordinator.

```
legata_to_rebeca (coordinator)
├── Step01 → init_agent           validate inputs, provision RMC, snapshot
├── Step02 → triage_agent         classify rule formalization status
├── Step03 → abstraction_agent    extract actors, discretize variables
├── Step04 → mapping_agent        generate .rebeca model + .property file
├── Step05 → synthesis_agent      LLM-assisted candidate generation (parallel)
├── Step06 → verification_agent   RMC + vacuity check + mutation scoring
├── Step07 → packaging_agent      collect and package artifacts
└── Step08 → reporting_agent      score (100-point rubric) + reports
```

## Agents & Skills

### Coordinator + Specialists

| Agent | Step | Description |
| :--- | :--- | :--- |
| `legata_to_rebeca` | Coordinator | Orchestrates Step01–Step08, manages shared_state |
| `init_agent` | Step01 | Validates inputs, provisions RMC, captures golden snapshot |
| `triage_agent` | Step02 | Classifies rule status: formalized / incomplete / incorrect / not-formalized |
| `abstraction_agent` | Step03 | Extracts actors, applies naming conventions, discretizes variables |
| `mapping_agent` | Step04 | Generates `.rebeca` model and `.property` file |
| `synthesis_agent` | Step05 | LLM-assisted candidate property generation (requires Step06 validation) |
| `verification_agent` | Step06 | Runs RMC, vacuity check, mutation scoring |
| `packaging_agent` | Step07 | Collects and packages pipeline artifacts |
| `reporting_agent` | Step08 | Produces per-rule scorecards and aggregate reports |

### Skills

| Skill | Used by | Purpose |
| :--- | :--- | :--- |
| `rebeca_tooling` | All specialists | Schemas + script documentation; 14 Python dumb tools |
| `rebeca_handbook` | abstraction, mapping, synthesis, verification, reporting | Modeling best practices |
| `legata_to_rebeca` | Coordinator | Workflow guidance |
| `rebeca_mutation` | verification_agent | Mutation testing patterns |
| `rebeca_hallucination` | verification_agent, reporting_agent | Hallucination detection patterns |

## Installation Details

`setup.py` installs agents and skills to `~/.agents/` (the primary truth copy) then creates platform-specific links:

| Target | Location | Format |
|--------|----------|--------|
| Claude Code | `.claude/agents/` | Symlinks; full frontmatter including `skills:` |
| Gemini CLI | `.gemini/agents/` | Physical copies; Gemini-incompatible keys stripped |
| GitHub Copilot | `.github/agents/` | Symlinks with `.agent.md` suffix |

`~/.agents/skills/` is a **shared namespace** — third-party skills (grepai, graphify) coexist with Rebeca's 5 owned skills. The installer only copies/links skills it owns and never overwrites unrelated entries.

## Requirements

- **Python 3.8+** | **Java 11+** (for RMC) | **C++ compiler** (g++/clang)
- **Platforms:** ✅ macOS · ✅ Linux · ✅ Windows

## Quick Links

- **[Installation Guide](docs/guides/installation.md)** — setup, flags, platform notes
- **[Usage Guide](docs/guides/usage.md)** — workflow examples
- **[Architecture](docs/guides/architecture.md)** — MAO design, SSOT, symlinking strategy
- **[Agent Reference](docs/agents/legata-to-rebeca.md)** — step bindings, frontmatter spec, output schema
- **[Scoring Contract](docs/SCORING.md)** — 100-point rubric definition

## Contributing

See [Contributing Guide](docs/guides/contributing.md) to learn how to add agents, skills, or dumb tools.
