# Installation Guide

Complete setup instructions for all platforms.

## Prerequisites

- **Python 3.8+** (cross-platform)
- **Java 11+** (for RMC model checker)
- **C++ compiler** (g++/clang for RMC compilation)

## Platform-Specific Setup

### Windows

**Option 1: Native Windows with MinGW**
```powershell
# Install prerequisites
choco install openjdk python3 mingw

# Verify installations
java -version
python3 --version
g++ --version
```

**Option 2: WSL2 (Recommended)**
```bash
# Install WSL2 with Ubuntu
wsl --install

# Inside WSL2, follow Linux instructions
sudo apt update
sudo apt install openjdk-17-jre python3 build-essential
```

### macOS

```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install prerequisites
brew install openjdk python3

# Install Xcode Command Line Tools
xcode-select --install

# Verify installations
java -version
python3 --version
g++ --version
```

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install openjdk-17-jre python3 python3-pip build-essential
```

### Linux (Fedora/RHEL)

```bash
sudo dnf install java-17-openjdk python3 gcc-c++
```

## One-Command Setup

### Option 1: Local Repository Installation (Recommended for Contributors)

```bash
git clone https://github.com/3brahimi/RebecAI.git
cd RebecAI

python3 setup.py
```

### Option 2: Remote Standalone Installation

```bash
curl -sSL https://raw.githubusercontent.com/3brahimi/RebecAI/main/setup.py | python3 -
```

Both methods:
1. Validate prerequisites (Java, Python, C++ compiler)
2. Copy all 9 agent definitions and 5 skills to `~/.agents/`
3. Create platform-specific target links (`.claude/`, `.gemini/`, `.github/`)
4. Download RMC from official GitHub releases

## Installation Flags

### `--mode` (local vs global)

```bash
python3 setup.py --mode local   # installs to .agents/ inside the repo (default)
python3 setup.py --mode global  # installs to ~/.agents/ (home directory)
```

Use `--mode global` for a shared installation accessible to all Claude Code sessions.

### `--dry-run` (preview without writing)

```bash
python3 setup.py --dry-run
```

Prints a comprehensive preview of what would be installed:

```
[1] Files copied to primary target (.agents/):
  agents/  (9 files)
    .agents/agents/legata_to_rebeca.md
    .agents/agents/init_agent.md
    ...
  skills/  (5 directories)
    .agents/skills/rebeca_tooling/
    ...

[2] Symlinks into AI agent roots:
  .claude  →  .agents
    agents/legata_to_rebeca.md  →  .agents/agents/legata_to_rebeca.md
    skills/rebeca_tooling/      →  .agents/skills/rebeca_tooling/
    ...
  .gemini  →  .agents
    agents/legata_to_rebeca.md  (physical copy, Gemini-compatible frontmatter)
    ...
  .github (GitHub/Copilot)
    agents/legata_to_rebeca.agent.md  →  .agents/agents/legata_to_rebeca.md
    instructions/  →  .agents/docs/
    ...

[3] RMC Model Checker:
    jar destination : .agents/rmc/rmc.jar
```

### `--no-rmc`

```bash
python3 setup.py --no-rmc
```

Skip RMC download (useful if already installed or in CI environments).

### `--rmc-tag`

```bash
python3 setup.py --rmc-tag v2.13
```

Pin a specific RMC release tag.

## What Gets Installed Where

### Shared Skills Namespace

`~/.agents/skills/` is a **shared namespace** — third-party tools like grepai and graphify may also install skills there. `setup.py` performs a **surgical per-skill install**, never wiping the whole directory:

- Rebeca's 5 owned skills are copied/replaced individually
- All other skills (grepai-*, graphify, etc.) are left untouched

### Target-Specific Agent Files

Each AI agent platform requires agents in a different format:

| Target | Location | Format |
|--------|----------|--------|
| Claude Code | `.claude/agents/` | Symlinks → `~/.agents/agents/`; full frontmatter |
| Gemini CLI | `.gemini/agents/` | **Physical copies** with Gemini-incompatible keys stripped |
| GitHub Copilot | `.github/agents/` | Symlinks with `.agent.md` suffix |

Gemini CLI may not follow symlinks in its agent registry, so `.gemini/agents/` receives real files. The keys `schema`, `skills`, `version`, and `user-invocable` are stripped from these copies because Gemini CLI only recognises `name`, `description`, `tools`, `model`, `max_turns`, `timeout_mins`, and `kind`.

### Skill Links

Only the 5 Rebeca-owned skills are linked to target skill directories. Third-party skills (grepai-*, graphify, etc.) are never linked to `.claude/skills/`, `.gemini/skills/`, or `.github/skills/` by this installer.

## Verify Installation

```bash
# Check all 9 agents installed
ls ~/.agents/agents/

# Check 5 owned skills installed
ls ~/.agents/skills/ | grep -E "^rebeca_|^legata_"

# Check RMC
java -jar ~/.agents/rmc/rmc.jar --version

# Check Claude Code sees agents
ls .claude/agents/

# Check Gemini CLI sees agents (physical copies)
ls .gemini/agents/
```

## Clean Re-Installation

```bash
python3 purge.py && python3 setup.py
```

`purge.py` surgically removes only the artifacts this repo installed (the 9 agents, 5 skills, docs, rmc, and rmc_path file). It reads the manifest from the repo's `agents/` and `skills/` source directories, so it will never accidentally remove third-party skills.

## Manual Installation

If you prefer manual setup:

### Step 1: Download RMC

```bash
python3 skills/rebeca_tooling/scripts/download_rmc.py \
  --dest-dir ~/.agents/rmc
```

### Step 2: Verify RMC

```bash
python3 skills/rebeca_tooling/scripts/verify_installation.py \
  --rmc-jar ~/.agents/rmc/rmc.jar
```

### Step 3: Install Agents and Skills

```bash
python3 skills/rebeca_tooling/scripts/install_artifacts.py \
  --target-root ~/.agents \
  --mode all
```

## Troubleshooting

### Java Not Found

```bash
java -version
# If not installed, see platform-specific setup above
```

### C++ Compiler Not Found

**macOS:**
```bash
xcode-select --install
```

**Linux:**
```bash
sudo apt install build-essential
```

**Windows:**
```powershell
choco install mingw
```

### RMC Download Failed

```bash
# Specify version explicitly
python3 skills/rebeca_tooling/scripts/download_rmc.py \
  --url https://github.com/rebeca-lang/org.rebecalang.rmc/releases/download/v2.8.2/rmc.jar \
  --dest-dir ~/.agents/rmc
```

### grepai/graphify Skills Missing After Install

`setup.py` does not manage third-party skills. If grepai or graphify skills are missing, re-run their own installers:

```bash
python3 -m setup_ai_search --platforms claude-cli,gemini-cli,github-copilot
```

## Next Steps

- [Usage Guide](usage.md) — learn how to use the agents and skills
- [Troubleshooting](troubleshooting.md) — common issues and fixes
