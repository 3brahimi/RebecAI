#!/usr/bin/env python3
"""
Claude Rebeca Setup Script

Automatically discovers and installs all agents and skills from the repository.
Downloads RMC model checker and verifies installation.
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


def setup(target_root: str = "~/.claude", rmc_tag: str | None = None) -> int:
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
  # Install to default location (~/.claude)
  python3 setup.py

  # Install to custom location
  python3 setup.py --target-root /path/to/install

  # Install specific RMC version
  python3 setup.py --rmc-tag v2.8.2
        """
    )
    parser.add_argument(
        "--target-root",
        default="~/.claude",
        help="Target installation directory (default: ~/.claude)"
    )
    parser.add_argument(
        "--rmc-tag",
        help="Specific RMC version tag (default: latest)"
    )

    args = parser.parse_args()

    # Support environment variables with proper defaults
    target_root = os.environ.get("CLAUDE_INSTALL_DIR") or args.target_root or "~/.claude"
    rmc_tag = os.environ.get("RMC_VERSION") or args.rmc_tag

    sys.exit(setup(target_root, rmc_tag))


if __name__ == "__main__":
    main()
