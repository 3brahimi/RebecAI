#!/usr/bin/env python3
"""
Setup Claude Rebeca: Install all agents, skills, and Model Checker.
Supports Claude Code, Gemini CLI, VS Code Copilot, and Codex CLI.
"""

import argparse
import os
import shutil
import sys
import re
from pathlib import Path
from typing import List, Tuple

# Add repository root to Python path
REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "rebeca-tooling" / "scripts"))

# Import tooling directly from the repo for the setup process
try:
    from download_rmc import download_rmc, is_valid_jar
    from utils import safe_path, resolve_executable
except ImportError:
    # Fallback if scripts/ is not yet in path or renamed
    sys.path.insert(0, str(REPO_ROOT / "skills" / "rebeca-tooling" / "lib"))
    from download_rmc import download_rmc, is_valid_jar
    from utils import safe_path, resolve_executable

# Target Conventions
AGENTS_ROOT_LOCAL = REPO_ROOT / ".agents"
AGENTS_ROOT_GLOBAL = Path.home() / ".agents"

CLAUDE_ROOT_LOCAL = REPO_ROOT / ".claude"
CLAUDE_ROOT_GLOBAL = Path.home() / ".claude"

GEMINI_ROOT_LOCAL = REPO_ROOT / ".gemini"
GEMINI_ROOT_GLOBAL = Path.home() / ".gemini"

GITHUB_ROOT = REPO_ROOT / ".github"

def lexists(path: Path) -> bool:
    return os.path.lexists(str(path))

def check_prerequisites() -> Tuple[bool, List[str]]:
    missing = []
    if sys.version_info < (3, 8): missing.append("Python 3.8+")
    if not resolve_executable("java"): missing.append("Java 11+ (JRE/JDK)")
    if not (resolve_executable("g++") or resolve_executable("clang++")):
        missing.append("C++ Compiler (g++ or clang)")
    return len(missing) == 0, missing

def discover_agents() -> List[Path]:
    return sorted(list((REPO_ROOT / "agents").glob("*.md"))) if (REPO_ROOT / "agents").exists() else []

def discover_skills() -> List[Path]:
    skills_dir = REPO_ROOT / "skills"
    if not skills_dir.exists(): return []
    return sorted([d for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()])

def patch_installed_paths(target_root: Path, rmc_jar_path: Path):
    """Patch placeholder RMC paths in installed files to the absolute path."""
    print(f"Patching RMC paths in {target_root}...")
    jar_path_str = str(rmc_jar_path.absolute())
    rmc_dir_str = str(rmc_jar_path.parent.absolute())

    JAR_PATTERN = re.compile(r'(?<![a-zA-Z0-9/])(?:\~?/\.claude|\~?/\.agents|\.claude|\.agents)/rmc/rmc\.jar')
    DIR_PATTERN = re.compile(r'(?<![a-zA-Z0-9/])(?:\~?/\.claude|\~?/\.agents|\.claude|\.agents)/rmc(?![/a-zA-Z0-9])')

    for f in target_root.rglob("*"):
        if f.is_file() and f.suffix in ('.md', '.py', '.sh', '.json'):
            try:
                content = f.read_text()
                new_content = JAR_PATTERN.sub(jar_path_str, content)
                new_content = DIR_PATTERN.sub(rmc_dir_str, new_content)
                if new_content != content:
                    f.write_text(new_content)
                    print(f"  ✓ Patched: {f.relative_to(target_root)}")
            except: pass

def create_surgical_symlink(src: Path, link: Path):
    """Create a symlink, removing existing files or directories if necessary."""
    if lexists(link):
        if link.is_symlink(): link.unlink()
        elif link.is_dir(): shutil.rmtree(link)
        else: link.unlink()
    
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Use relative paths for local installs, absolute for global
        if str(Path.home()) in str(src) and "/.agents" in str(src):
            os.symlink(src, link, target_is_directory=src.is_dir())
        else:
            rel_src = os.path.relpath(src, link.parent)
            os.symlink(rel_src, link, target_is_directory=src.is_dir())
        print(f"  ✓ Linked: {link.name}")
    except (OSError, NotImplementedError):
        if src.is_dir(): shutil.copytree(src, link)
        else: shutil.copy2(src, link)
        print(f"  ✓ Copied: {link.name}")

def install_to_agents(agents: List[Path], skills: List[Path], target_root: Path):
    """Install implementations to the primary truth directory."""
    print(f"Installing to {target_root} (Master Source)...")
    target_root.mkdir(parents=True, exist_ok=True)
    for sub in ("agents", "skills"): (target_root / sub).mkdir(parents=True, exist_ok=True)
    
    for agent in agents:
        shutil.copy2(agent, target_root / "agents" / agent.name)
        print(f"  ✓ Agent: {agent.name}")
        
    for skill in skills:
        dest = target_root / "skills" / skill.name
        if dest.exists(): shutil.rmtree(dest)
        shutil.copytree(skill, dest)
        print(f"  ✓ Skill: {skill.name}")

def link_to_target(target_root: Path, primary_truth: Path):
    """Surgically link files from the truth store into a target root."""
    if not target_root: return
    print(f"Linking {target_root} -> {primary_truth}...")
    
    # If the root itself is a symlink, we must convert it back to a real directory
    if target_root.is_symlink():
        target_root.unlink()
    target_root.mkdir(parents=True, exist_ok=True)

    # Link Agents
    for agent in (primary_truth / "agents").glob("*.md"):
        # Handle Copilot agent naming convention
        link_name = agent.name if ".github" not in str(target_root) else agent.stem + ".agent.md"
        create_surgical_symlink(agent, target_root / "agents" / link_name)

    # Link Skills
    for skill in (primary_truth / "skills").iterdir():
        if skill.is_dir():
            create_surgical_symlink(skill, target_root / "skills" / skill.name)

    # Link Instructions (Copilot only)
    if ".github" in str(target_root):
        create_surgical_symlink(REPO_ROOT / "docs", target_root / "instructions")

def main():
    parser = argparse.ArgumentParser(description="Setup Claude Rebeca for multiple AI agents")
    parser.add_argument("--mode", choices=["local", "global"], default="local")
    parser.add_argument("--target-root", default=None)
    parser.add_argument("--rmc-tag", default=None)
    parser.add_argument("--no-rmc", action="store_true")
    args = parser.parse_args()

    print(f"🚀 Initializing Claude Rebeca Multi-Target Setup ({args.mode})")
    print("-----------------------------------------------")

    ok, missing = check_prerequisites()
    if not ok:
        print("❌ Missing prerequisites:"); [print(f"  - {i}") for i in missing]; return 1

    agents = discover_agents()
    skills = discover_skills()

    if args.target_root:
        primary_target = Path(args.target_root)
        targets = []
    else:
        primary_target = AGENTS_ROOT_LOCAL if args.mode == "local" else AGENTS_ROOT_GLOBAL
        targets = [
            (CLAUDE_ROOT_LOCAL if args.mode == "local" else CLAUDE_ROOT_GLOBAL),
            (GEMINI_ROOT_LOCAL if args.mode == "local" else GEMINI_ROOT_GLOBAL)
        ]
        if args.mode == "local": targets.append(GITHUB_ROOT)

    # 1. Install Master Truth
    install_to_agents(agents, skills, primary_target)

    # 2. Surgically link into other agent directories
    for t in targets:
        link_to_target(t, primary_target)

    # 3. Provision RMC
    rmc_jar_path = None
    if not args.no_rmc:
        print("\n📦 Provisioning RMC Model Checker...")
        rmc_dest = primary_target / "rmc"
        rmc_dest.mkdir(parents=True, exist_ok=True)
        rmc_url = "https://github.com/rebeca-lang/org.rebecalang.rmc/releases/" + ("latest" if not args.rmc_tag else "")
        result = download_rmc(rmc_url, str(rmc_dest), tag=args.rmc_tag)
        if result == 0:
            rmc_jar_path = rmc_dest / "rmc.jar"
            with open(primary_target / "rmc_path", "w") as f: f.write(str(rmc_jar_path))
            print("  ✓ RMC provisioned successfully")
    
    if rmc_jar_path: patch_installed_paths(primary_target, rmc_jar_path)

    print("\n✅ Setup Complete!")
    print(f"Truth Store: {primary_target}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
