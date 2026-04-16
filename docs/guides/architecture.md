# Architecture Guide

System design and component overview for RebecAI.

## Overview

RebecAI follows a **Multi-Agent Orchestration (MAO)** architecture with three main layers:

1. **Agent Layer** — one coordinator + eight specialist subagents
2. **Skills Layer** — reusable knowledge injected into subagent system prompts
3. **Tooling Layer** — deterministic Python scripts ("dumb tools") invoked via `Bash`

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                       Agent Layer                           │
│                                                             │
│   legata_to_rebeca (coordinator)                            │
│   ┌──────────┬──────────┬──────────┬──────────────────┐    │
│   │Step01    │Step02    │Step03    │ Step04 ║ Step05   │    │
│   │init      │triage    │abstract  │ mapping║synthesis │    │
│   │_agent    │_agent    │_agent    │ _agent ║ _agent   │    │
│   └──────────┴──────────┴──────────┴──────────────────┘    │
│   ┌──────────────────────────────────────────────────┐      │
│   │Step06             │Step07          │Step08        │      │
│   │verification_agent │packaging_agent │reporting_    │      │
│   │                   │                │agent         │      │
│   └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
                          │ skills: injects SKILL.md at startup
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      Skills Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ legata_to_   │  │   rebeca_    │  │   rebeca_    │      │
│  │   rebeca     │  │  handbook    │  │   tooling    │      │
│  │              │  │              │  │              │      │
│  │ Workflow     │  │ Modeling     │  │ Schemas +    │      │
│  │ guidance     │  │ best         │  │ script docs  │      │
│  │              │  │ practices    │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                          │ Bash tool calls
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     Tooling Layer                           │
│  skills/rebeca_tooling/scripts/  (dumb deterministic tools) │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  pre_run_rmc_check.py    verify_installation.py     │    │
│  │  snapshotter.py          classify_rule_status.py    │    │
│  │  colreg_fallback_mapper.py  run_rmc.py              │    │
│  │  vacuity_checker.py      mutation_engine.py         │    │
│  │  install_artifacts.py    score_single_rule.py       │    │
│  │  generate_report.py      symbol_differ.py           │    │
│  │  utils.py (security guards)                         │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Root utilities (not installed):                            │
│  - setup.py   (one-command installer, --dry-run supported)  │
│  - purge.py   (surgical cleanup of owned artifacts only)    │
└─────────────────────────────────────────────────────────────┘
```

## Design Principles

### 1. Multi-Agent Orchestration (MAO)
- The coordinator (`legata_to_rebeca`) drives the workflow and manages `shared_state`
- Each step is delegated to a **specialist subagent** running in its own context window
- Specialists call **dumb deterministic Python scripts** via the `Bash` tool — no LLM logic inside the scripts
- Each specialist emits a **structured JSON contract** that the coordinator validates before advancing

### 2. Single Source of Truth (SSOT)
- All agent and skill definitions live in the repo's `agents/` and `skills/` directories
- `setup.py` installs them to `~/.agents/` (the primary truth copy)
- From `~/.agents/`, `setup.py` creates target-specific links to `.claude/`, `.gemini/`, `.github/`
- Never edit files directly in target directories — always edit the source and re-run `setup.py`

### 3. Shared Skills Namespace
- `~/.agents/skills/` is a **shared namespace** across all projects and tools
- Third-party skills (grepai, graphify, etc.) coexist alongside Rebeca's 5 owned skills
- `setup.py` performs surgical per-skill copies — it never wipes the whole `skills/` directory
- `purge.py` only removes skills this repo owns (derived from `skills/` in the repo root)

### 4. Cross-Platform Symlinking
- **`.claude/agents/`** — symlinks to `~/.agents/agents/`; full frontmatter including `skills:` (valid Claude Code key)
- **`.gemini/agents/`** — **physical copies** with Gemini-incompatible keys stripped (`schema`, `skills`, `version`, `user-invocable`); Gemini CLI may not follow symlinks
- **`.github/agents/`** — symlinks with `.agent.md` extension suffix for Copilot discovery

### 5. Separation of Concerns
- **Coordinator** — state machine, routing, error handling, budget tracking
- **Specialists** — focused context windows, call tools, return JSON
- **Dumb tools** — deterministic Python scripts, no LLM involvement
- **Skills** — knowledge injected as system prompt content at startup

## Workflow Execution

```
User → @legata_to_rebeca
         │
         ▼
  Coordinator reads shared_state
         │
   ┌─────▼─────┐
   │  Step01   │ → init_agent → JSON → shared_state.step01
   └─────┬─────┘
   ┌─────▼─────┐
   │  Step02   │ → triage_agent → JSON → shared_state.step02
   └─────┬─────┘
   ┌─────▼─────┐
   │  Step03   │ → abstraction_agent → JSON → shared_state.step03
   └─────┬─────┘
   ┌────────────────────────────────────┐
   │  Step04 ║ Step05 (parallel)       │
   │  mapping_agent ║ synthesis_agent  │
   └────────────────────────────────────┘
         │
   ┌─────▼─────┐
   │  Step06   │ → verification_agent → JSON → shared_state.step06
   └─────┬─────┘
   ┌─────▼─────┐
   │  Step07   │ → packaging_agent → JSON → shared_state.step07
   └─────┬─────┘
   ┌─────▼─────┐
   │  Step08   │ → reporting_agent → scorecard.json + report.md
   └───────────┘
```

## Data Flow

### Input
1. **Legata rule file** — formal specification
2. **Reference model** — base `.rebeca` file
3. **Reference property** — base `.property` file

### Processing (Step01–Step08)
1. **Step01** — validate inputs, provision RMC, snapshot golden state
2. **Step02** — classify rule status, attach defect evidence
3. **Step03** — extract actors, discretize variables
4. **Step04/05** — generate `.rebeca` model and `.property` file (Step05 in parallel, produces candidates only)
5. **Step06** — run RMC, vacuity check, mutation scoring
6. **Step07** — collect and package artifacts
7. **Step08** — score and generate reports

### Output
1. **Model files** — `.rebeca` and `.property`
2. **Verification logs** — RMC stdout/stderr
3. **Scorecards** — JSON per-rule scoring
4. **Reports** — aggregate JSON and Markdown

## Agent Frontmatter Spec

Agent files use YAML frontmatter. The recognized keys differ by platform:

| Key | Claude Code | Gemini CLI | Used in source |
|-----|------------|------------|----------------|
| `name` | Required | Required | ✓ |
| `description` | Required | Required | ✓ |
| `skills` | Valid — injects SKILL.md at startup | Not standard | ✓ (Claude only) |
| `schema` | Tolerated (unknown key) | Stripped | ✓ internal pointer |
| `tools` | Valid — allowlist | Valid | Omitted (inherits all) |
| `model` | Valid | Valid | Omitted (inherits) |
| `version` | Not standard | Not standard | Removed |
| `user-invocable` | Not standard | Not standard | Removed |

The `_write_gemini_agent` function in `setup.py` strips `schema`, `skills`, `version`, and `user-invocable` when writing physical copies to `.gemini/agents/`.

## RMC Workflow

### Critical Phases

1. **Parse** — RMC parses `.rebeca` and `.property` (exit code 5 on syntax error)
2. **Generate** — RMC generates C++ source files (`-x` flag)
3. **Compile** — g++ compiles C++ to executable (exit code 4 on failure)
4. **Execute** — run executable for verification (counterexample if property violated)

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
claude-rebeca/
├── agents/                              # 9 agent definitions (source)
│   ├── legata_to_rebeca.md             # Coordinator
│   ├── init_agent.md
│   ├── triage_agent.md
│   ├── abstraction_agent.md
│   ├── mapping_agent.md
│   ├── synthesis_agent.md
│   ├── verification_agent.md
│   ├── packaging_agent.md
│   └── reporting_agent.md
├── skills/                              # 5 owned skills (source)
│   ├── legata_to_rebeca/SKILL.md
│   ├── rebeca_handbook/SKILL.md
│   ├── rebeca_tooling/
│   │   ├── SKILL.md
│   │   ├── schemas/                     # JSON output schemas per agent
│   │   └── scripts/                     # Dumb tools (14 Python modules)
│   ├── rebeca_mutation/
│   └── rebeca_hallucination/
├── docs/                                # Developer documentation
├── tests/                               # pytest suite (incl. E2E DAG tests)
├── setup.py                             # One-command installer (--dry-run)
└── purge.py                             # Surgical cleanup (owned artifacts only)

# Primary truth copy (after setup.py)
~/.agents/
├── agents/          # All 9 .md files (physical copies from source)
├── skills/          # Shared namespace: 5 Rebeca skills + third-party
│   ├── rebeca_tooling/
│   ├── rebeca_handbook/
│   ├── legata_to_rebeca/
│   ├── rebeca_mutation/
│   ├── rebeca_hallucination/
│   └── grepai-*/   # Third-party (installed by setup_ai_search, not touched)
├── docs/            # Docs copy (symlink target for .github/instructions)
└── rmc/rmc.jar      # RMC model checker

# Target links
~/.claude/agents/    # Symlinks → ~/.agents/agents/
~/.claude/skills/    # Symlinks → ~/.agents/skills/ (owned skills only)
~/.gemini/agents/    # Physical copies with Gemini-compatible frontmatter
~/.gemini/skills/    # Symlinks → ~/.agents/skills/ (owned skills only)
~/.github/agents/    # Symlinks with .agent.md suffix
~/.github/skills/    # Symlinks → ~/.agents/skills/ (owned skills only)
~/.github/instructions/ → ~/.agents/docs/
```

## Installed Paths

After running `python3 setup.py --mode global`:

| Artifact | Installed Path |
|----------|---------------|
| Coordinator | `~/.agents/agents/legata_to_rebeca.md` |
| Specialist agents (×8) | `~/.agents/agents/<agent>.md` |
| Workflow guidance skill | `~/.agents/skills/legata_to_rebeca/` |
| Modeling handbook skill | `~/.agents/skills/rebeca_handbook/` |
| Tooling skill + scripts | `~/.agents/skills/rebeca_tooling/` |
| Mutation skill | `~/.agents/skills/rebeca_mutation/` |
| Hallucination skill | `~/.agents/skills/rebeca_hallucination/` |
| RMC model checker | `~/.agents/rmc/rmc.jar` |

## Testing Strategy

### E2E Integration Tests (`tests/test_coordinator_e2e.py`)
- CLI-based DAG integration test — each step invokes the Python scripts via `subprocess.run`
- Pre-computed fixtures for LLM-dependent steps (Step03, Step05)
- `@pytest.mark.requires_rmc` skips RMC-dependent tests when `~/.rebeca/rmc.jar` is absent
- Module-scoped `pipeline` fixture accumulates state across step classes

### Unit Tests
- Per-script tests for classify, score, mutate, vacuity
- Mock RMC execution for speed

## Security Considerations

- Input validation via `utils.py` security guards before any subprocess execution
- No credentials in code; no network calls except RMC download
- `purge.py` performs surgical removal — never blindly wipes directories it doesn't own

## Next Steps

- [API Reference](api-reference.md) — complete function signatures
- [Contributing Guide](contributing.md) — how to extend the system
