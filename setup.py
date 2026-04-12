#!/usr/bin/env python3
"""
Claude Rebeca Setup Script

Automatically discovers and installs all agents and skills from the repository.
Downloads RMC model checker and verifies installation.

Modes:
  local   Install to .claude/ relative to CWD (per-project use)
  global  Install to ~/.claude/ (system-wide Claude Code use)
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple
import shutil
import sys

# Add repository root to Python path
REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "rebeca-tooling" / "lib"))

from download_rmc import download_rmc, is_valid_jar
from utils import safe_path, resolve_executable

LOCAL_TARGET = Path.cwd() / ".claude"
GLOBAL_TARGET = Path.home() / ".claude"


def check_prerequisites() -> Tuple[bool, List[str]]:
    """Check if required dependencies are installed."""
    missing = []

    # Check Java
    try:
        subprocess.run([resolve_executable("java"), "-version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing.append("java")

    # Check Python version
    if sys.version_info < (3, 8):
        missing.append("python3.8+")

    # Check g++ or clang++
    has_cpp = False
    for compiler in ["g++", "clang++"]:
        try:
            subprocess.run([resolve_executable(compiler), "--version"], capture_output=True, check=True)
            has_cpp = True
            break
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    if not has_cpp:
        missing.append("g++/clang++")

    return len(missing) == 0, missing


def discover_agents() -> List[Path]:
    """Discover all agent files in agents/ directory."""
    agents_dir = REPO_ROOT / "agents"
    if not agents_dir.exists():
        return []

    agents = list(agents_dir.glob("*.md"))
    return sorted(agents)


def discover_skills() -> List[Path]:
    """Discover all skill directories in skills/ directory."""
    skills_dir = REPO_ROOT / "skills"
    if not skills_dir.exists():
        return []

    # A skill is a directory containing SKILL.md
    skills = [d for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]
    return sorted(skills)


def install_agents(agents: List[Path], target_root: Path) -> int:
    """Install discovered agents to target directory."""
    if not agents:
        print("  No agents found to install")
        return 0

    agents_dest = target_root / "agents"
    agents_dest.mkdir(parents=True, exist_ok=True)

    installed = 0
    for agent in agents:
        try:
            shutil.copy2(agent, agents_dest / agent.name)
            print(f"  ✓ {agent.name}")
            installed += 1
        except Exception as e:
            print(f"  ✗ {agent.name}: {e}", file=sys.stderr)

    return installed


def install_skills(skills: List[Path], target_root: Path) -> int:
    """Install discovered skills to target directory."""
    if not skills:
        print("  No skills found to install")
        return 0

    skills_dest = target_root / "skills"
    skills_dest.mkdir(parents=True, exist_ok=True)

    installed = 0
    for skill in skills:
        try:
            dest = skills_dest / skill.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(skill, dest)
            print(f"  ✓ {skill.name}/")
            installed += 1
        except Exception as e:
            print(f"  ✗ {skill.name}/: {e}", file=sys.stderr)

    return installed


def patch_installed_paths(target_path: Path, rmc_jar: Path) -> None:
    """
    Rewrite placeholder RMC paths in installed agent and skill files.

    Source files use .claude/rmc/rmc.jar as a placeholder.
    After install, replace with the actual absolute path so agents
    and skills work regardless of local vs global install mode.
    """
    PLACEHOLDER = ".claude/rmc/rmc.jar"
    PLACEHOLDER_DIR = ".claude/rmc"
    actual_jar = str(rmc_jar)
    actual_dir = str(rmc_jar.parent)

    patched = 0
    for pattern in ["**/*.md", "**/*.py", "**/*.json", "**/*.sh"]:
        for f in target_path.glob(pattern):
            if not f.is_file():
                continue
            try:
                text = f.read_text()
                if PLACEHOLDER in text or PLACEHOLDER_DIR in text:
                    # Use a sentinel to avoid double-substitution:
                    # replace the full jar path first, then the dir-only placeholder
                    sentinel = "__RMC_JAR_SENTINEL__"
                    text = text.replace(PLACEHOLDER, sentinel)
                    text = text.replace(PLACEHOLDER_DIR, actual_dir)
                    text = text.replace(sentinel, actual_jar)
                    f.write_text(text)
                    patched += 1
            except Exception as e:
                print(f"  ⚠ Could not patch {f}: {e}", file=sys.stderr)

    print(f"  ✓ Patched RMC paths in {patched} installed file(s) → {actual_jar}")


def write_rmc_path_marker(target_path: Path, rmc_jar: Path) -> None:
    """Write absolute rmc.jar path to .claude/rmc_path for runtime consumers."""
    marker = target_path / "rmc_path"
    marker.write_text(str(rmc_jar))
    print(f"  ✓ RMC path marker written to {marker}")


def verify_rmc_installation(rmc_dest: Path) -> bool:
    """Verify RMC is installed and executable."""
    jar_path = rmc_dest / "rmc.jar"

    if not is_valid_jar(jar_path):
        print(f"  ✗ rmc.jar not found or invalid at {jar_path}", file=sys.stderr)
        return False

    # Test RMC execution
    try:
        result = subprocess.run(
            [resolve_executable("java"), "-jar", str(jar_path), "-h"],
            capture_output=True,
            timeout=5
        )
        if result.returncode != 0:
            print("  ✗ RMC execution test failed (java -jar rmc.jar -h)", file=sys.stderr)
            return False
    except Exception as e:
        print(f"  ✗ RMC execution test failed: {e}", file=sys.stderr)
        return False

    print("  ✓ RMC verified and executable")
    return True


def setup(target_root: str = ".claude", rmc_tag: str | None = None) -> int:
    """
    Main setup function: discover and install all agents/skills, download RMC.

    Returns:
        0: Success
        1: Prerequisites missing
        2: RMC download failed
        3: RMC verification failed
        4: Artifact installation failed
    """
    print("=" * 60)
    print("Claude Rebeca Setup")
    print("=" * 60)
    print()

    # Expand and validate target path
    target_path = safe_path(target_root)

    # Step 1: Check prerequisites
    print("[1/4] Checking prerequisites...")
    prereqs_ok, missing = check_prerequisites()

    if not prereqs_ok:
        print(f"  ✗ Missing required dependencies: {', '.join(missing)}")
        print()
        print("Install instructions:")
        print("  Ubuntu/Debian: sudo apt install openjdk-17-jre python3 build-essential")
        print("  macOS: brew install openjdk python3 && xcode-select --install")
        print("  Fedora/RHEL: sudo dnf install java-17-openjdk python3 gcc-c++")
        print("  Windows: Install via WSL2 and follow Linux instructions")
        return 1

    print("  ✓ All prerequisites satisfied")
    print()

    # Step 2: Download RMC
    print("[2/4] Downloading RMC...")
    rmc_dest = target_path / "rmc"

    url = "https://github.com/rebeca-lang/org.rebecalang.rmc/releases/latest"
    result = download_rmc(url, str(rmc_dest), tag=rmc_tag)

    if result != 0:
        print("  ✗ RMC download failed")
        return 2

    print(f"  ✓ RMC downloaded to {rmc_dest}/rmc.jar")
    print()

    # Step 3: Verify RMC installation
    print("[3/4] Verifying RMC installation...")
    if not verify_rmc_installation(rmc_dest):
        return 3
    write_rmc_path_marker(target_path, rmc_dest / "rmc.jar")
    print()

    # Step 4: Discover and install agents/skills
    print("[4/4] Installing agents and skills...")

    # Discover
    agents = discover_agents()
    skills = discover_skills()

    print(f"  Discovered {len(agents)} agent(s) and {len(skills)} skill(s)")
    print()

    # Install agents
    if agents:
        print("  Installing agents:")
        agents_installed = install_agents(agents, target_path)
    else:
        agents_installed = 0

    print()

    # Install skills
    if skills:
        print("  Installing skills:")
        skills_installed = install_skills(skills, target_path)
    else:
        skills_installed = 0

    print()

    if agents_installed == 0 and skills_installed == 0:
        print("  ✗ No artifacts were installed")
        return 4

    # Patch placeholder RMC paths in all installed files
    print("  Patching RMC paths in installed artifacts...")
    patch_installed_paths(target_path, rmc_dest / "rmc.jar")
    print()

    # Summary
    print("=" * 60)
    print("Setup Complete")
    print("=" * 60)
    print()
    print(f"Installation directory: {target_path}")
    print()
    print("Installed artifacts:")
    print(f"  Agents: {agents_installed}")
    for agent in agents:
        print(f"    - {agent.name}")
    print()
    print(f"  Skills: {skills_installed}")
    for skill in skills:
        print(f"    - {skill.name}/")
    print()
    print(f"  RMC: {rmc_dest}/rmc.jar")
    print()
    print("Next steps:")
    print("  1. Verify installation:")
    print(f"     ls {target_path}/agents/")
    print(f"     ls {target_path}/skills/")
    print()
    print("  2. Run tests:")
    print("     bash tests/run_full_acceptance_tests.sh")
    print()
    print("  3. Use the agent:")
    print("     @legata-to-rebeca Transform legata/Rule-22.legata to Rebeca.")
    print()

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Setup Claude Rebeca: Install all agents, skills, and RMC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local install (default) — installs to .claude/ in CWD
  python3 setup.py

  # Global install — installs to ~/.claude/ for system-wide Claude Code use
  python3 setup.py --mode global

  # Custom location
  python3 setup.py --target-root /path/to/install

  # Pin specific RMC version
  python3 setup.py --rmc-tag v2.8.2
        """
    )
    parser.add_argument(
        "--mode",
        choices=["local", "global"],
        default="local",
        help="Install mode: local (.claude/ in CWD) or global (~/.claude/). Default: local"
    )
    parser.add_argument(
        "--target-root",
        default=None,
        help="Override install directory (overrides --mode)"
    )
    parser.add_argument(
        "--rmc-tag",
        help="Specific RMC version tag (default: latest)"
    )

    args = parser.parse_args()

    # Resolve target root: explicit flag > env var > mode default
    if args.target_root:
        target_root = args.target_root
    elif os.environ.get("CLAUDE_INSTALL_DIR"):
        target_root = os.environ["CLAUDE_INSTALL_DIR"]
    elif args.mode == "global":
        target_root = str(GLOBAL_TARGET)
    else:
        target_root = str(LOCAL_TARGET)

    rmc_tag = os.environ.get("RMC_VERSION") or args.rmc_tag

    print(f"Install mode : {args.mode}")
    print(f"Install target: {target_root}")
    print()

    sys.exit(setup(target_root, rmc_tag))


if __name__ == "__main__":
    main()
