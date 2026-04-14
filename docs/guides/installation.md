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
# Update package list
sudo apt update

# Install prerequisites
sudo apt install openjdk-17-jre python3 python3-pip build-essential

# Verify installations
java -version
python3 --version
g++ --version
```

### Linux (Fedora/RHEL)

```bash
# Install prerequisites
sudo dnf install java-17-openjdk python3 gcc-c++

# Verify installations
java -version
python3 --version
g++ --version
```

## One-Command Setup

After prerequisites are installed, you can set up the environment using one of the following methods:

### Option 1: Local Repository Installation (Recommended for Contributors)

```bash
# Clone repository
git clone https://github.com/3brahimi/RebecAI.git
cd RebecAI

# Run setup script
python3 setup.py
```

### Option 2: Remote Standalone Installation (Fastest for Users)

If you only want to install the agents and skills without cloning the full repository, you can run the installer directly from GitHub:

```bash
curl -sSL https://raw.githubusercontent.com/3brahimi/RebecAI/main/setup.py | python3 -
```

*Note: This method downloads the project as a ZIP, extracts the necessary artifacts, and links them to your AI agent configuration folders (`~/.agents/`, etc.).*

Both methods will:
1. Check prerequisites (Java, Python, C++ compiler)
2. Download RMC from official GitHub releases
3. Verify RMC installation
4. Auto-discover and install all agents and skills to `~/.agents/`

## Manual Installation

If you prefer manual setup:

### Step 1: Download RMC

```bash
python3 skills/rebeca-tooling/scripts/download_rmc.py \
  --url https://github.com/rebeca-lang/org.rebecalang.rmc/releases/latest \
  --dest-dir ~/.agents/rmc
```

### Step 2: Verify RMC

```bash
python3 skills/rebeca-tooling/scripts/verify_installation.py \
  --rmc-jar ~/.agents/rmc/rmc.jar
```

### Step 3: Install Agents and Skills

```bash
python3 skills/rebeca-tooling/scripts/install_artifacts.py \
  --target-root ~/.agents \
  --mode all
```

## Verify Installation

```bash
# Check RMC
java -jar ~/.agents/rmc/rmc.jar --version

# Check agents
ls ~/.agents/agents/

# Check skills
ls ~/.agents/skills/
```

## Clean Re-Installation

To remove all previously installed artifacts before a fresh install (e.g., after updating the repository):

```bash
python3 purge.py
python3 setup.py
```

`purge.py` surgically removes only the artifacts registered by the installer, leaving unrelated files untouched.

## Troubleshooting

### Java Not Found

```bash
# Check Java installation
java -version

# If not installed, see platform-specific setup above
```

### C++ Compiler Not Found

**Windows:**
```powershell
# Install MinGW
choco install mingw

# Or use WSL2
```

**macOS:**
```bash
# Install Xcode Command Line Tools
xcode-select --install
```

**Linux:**
```bash
# Install build-essential
sudo apt install build-essential
```

### RMC Download Failed

```bash
# Manual download
wget https://github.com/rebeca-lang/org.rebecalang.rmc/releases/download/v2.8.2/rmc.jar -O ~/.agents/rmc/rmc.jar

# Or specify version explicitly
python3 skills/rebeca-tooling/lib/download_rmc.py \
  --url https://github.com/rebeca-lang/org.rebecalang.rmc/releases/download/v2.8.2/rmc.jar \
  --dest-dir ~/.agents/rmc
```

## Next Steps

- [Usage Guide](usage.md) - Learn how to use the agents and skills
- [Troubleshooting](troubleshooting.md) - Common issues and fixes
