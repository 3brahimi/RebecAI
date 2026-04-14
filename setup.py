#!/usr/bin/env python3
"""
Claude Rebeca Standalone Installer
One-liner: curl -sSL <url>/setup.py | python3 -

Surgically installs maritime safety agents and skills from the master 
GitHub repository into .agents, .claude, .gemini, and .github.
"""

import argparse
import os
import shutil
import sys
import re
import urllib.request
import zipfile
import tempfile
from pathlib import Path
from typing import List, Tuple

# Configuration
GITHUB_REPO = "3brahimi/RebecAI"
ZIP_URL = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/main.zip"
RMC_LATEST_URL = "https://github.com/rebeca-lang/org.rebecalang.rmc/releases/latest"

# Target Conventions
HOME = Path.home()
REPO_ROOT = Path.cwd()

# Implementation Path Truths (Master Source)
AGENTS_ROOT_LOCAL = REPO_ROOT / ".agents"
AGENTS_ROOT_GLOBAL = HOME / ".agents"

# AI Agent Specific Paths
CLAUDE_ROOT_LOCAL = REPO_ROOT / ".claude"
CLAUDE_ROOT_GLOBAL = HOME / ".claude"
GEMINI_ROOT_LOCAL = REPO_ROOT / ".gemini"
GEMINI_ROOT_GLOBAL = HOME / ".gemini"
GITHUB_ROOT = REPO_ROOT / ".github"

# --- STANDALONE UTILITIES (Formerly in utils.py/download_rmc.py) ---

def resolve_executable(name: str) -> str:
    return shutil.which(name)

def download_file(url: str, dest: Path) -> bool:
    print(f"  Downloading: {url}")
    try:
        with urllib.request.urlopen(url) as response, open(dest, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        return True
    except Exception as e:
        print(f"  ❌ Download failed: {e}")
        return False

def lexists(path: Path) -> bool:
    return os.path.lexists(str(path))

# --- CORE INSTALLATION LOGIC ---

def create_surgical_symlink(src: Path, link: Path):
    if lexists(link):
        if link.is_symlink(): link.unlink()
        elif link.is_dir(): shutil.rmtree(link)
        else: link.unlink()
    
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Relative paths for local, absolute for global
        if str(HOME) in str(src) and "/.agents" in str(src):
            os.symlink(src, link, target_is_directory=src.is_dir())
        else:
            rel_src = os.path.relpath(src, link.parent)
            os.symlink(rel_src, link, target_is_directory=src.is_dir())
        print(f"    ✓ Linked: {link.name}")
    except:
        if src.is_dir(): shutil.copytree(src, link)
        else: shutil.copy2(src, link)
        print(f"    ✓ Copied: {link.name}")

def link_to_target(target_root: Path, primary_truth: Path, is_github: bool = False):
    if not target_root: return
    print(f"  Linking to {target_root}...")
    
    if target_root.is_symlink(): target_root.unlink()
    target_root.mkdir(parents=True, exist_ok=True)

    # 1. Link Agents
    for agent in (primary_truth / "agents").glob("*.md"):
        link_name = agent.name if not is_github else agent.stem + ".agent.md"
        create_surgical_symlink(agent, target_root / "agents" / link_name)

    # 2. Link Skills
    for skill in (primary_truth / "skills").iterdir():
        if skill.is_dir():
            create_surgical_symlink(skill, target_root / "skills" / skill.name)

    # 3. Link Instructions (Copilot/Github only)
    if is_github:
        # Note: Standalone installer might not have full docs if ZIP was minimal,
        # but we download the full project zip so it should be there.
        docs_src = primary_truth / "docs"
        if docs_src.exists():
            create_surgical_symlink(docs_src, target_root / "instructions")

def patch_rmc_paths(target_root: Path, rmc_jar_path: Path):
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
                if new_content != content: f.write_text(new_content)
            except: pass

def main():
    parser = argparse.ArgumentParser(description="Standalone Maritime Agent Installer")
    parser.add_argument("--mode", choices=["local", "global"], default="local")
    parser.add_argument("--no-rmc", action="store_true")
    args = parser.parse_args()

    print(f"🚀 Initializing Claude Rebeca Standalone Installer ({args.mode})")
    print("---------------------------------------------------------")

    # 1. Determine local source or bootstrap from GitHub
    local_src = Path(__file__).parent
    if (local_src / "agents").exists() and (local_src / "skills").exists():
        print("  ✓ Running in Repo-Local mode")
        src_root = local_src
    else:
        print("  ☁ Running in Remote-Bootstrap mode")
        tmp_dir = Path(tempfile.mkdtemp())
        zip_path = tmp_dir / "repo.zip"
        if not download_file(ZIP_URL, zip_path): return 1
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmp_dir)
        
        # GitHub ZIPs usually have a top-level folder 'repo-main'
        extracted_dirs = [d for d in tmp_dir.iterdir() if d.is_dir()]
        src_root = extracted_dirs[0] if extracted_dirs else tmp_dir

    # 2. Define Primary Target
    primary_target = AGENTS_ROOT_LOCAL if args.mode == "local" else AGENTS_ROOT_GLOBAL
    primary_target.mkdir(parents=True, exist_ok=True)
    
    # 3. Install Master Truth
    print(f"  Installing Master Source to {primary_target}...")
    for sub in ("agents", "skills", "docs"):
        dest = primary_target / sub
        if dest.exists(): shutil.rmtree(dest)
        if (src_root / sub).exists():
            shutil.copytree(src_root / sub, dest)
    
    # 4. Surgical Symlinking to AI Agents
    targets = [
        (CLAUDE_ROOT_LOCAL if args.mode == "local" else CLAUDE_ROOT_GLOBAL, False),
        (GEMINI_ROOT_LOCAL if args.mode == "local" else GEMINI_ROOT_GLOBAL, False),
    ]
    if args.mode == "local": targets.append((GITHUB_ROOT, True))

    for t_root, is_github in targets:
        link_to_target(t_root, primary_target, is_github)

    # 5. Provision RMC Toolchain
    rmc_jar_path = None
    if not args.no_rmc:
        print("\n📦 Provisioning RMC Model Checker...")
        rmc_dest = primary_target / "rmc"
        rmc_dest.mkdir(parents=True, exist_ok=True)
        
        # Simplified standalone RMC download
        # (Assuming latest release jar is named rmc.jar or we can find it)
        # For simplicity in standalone, we use the known latest direct JAR link if possible
        # Or just download the latest release and find the jar.
        # This part requires the actual RMC direct download URL.
        # Use the latest released JAR from Rebeca Lang
        jar_url = "https://github.com/rebeca-lang/org.rebecalang.rmc/releases/latest/download/rmc.jar"
        rmc_jar_path = rmc_dest / "rmc.jar"
        if download_file(jar_url, rmc_jar_path):
            with open(primary_target / "rmc_path", "w") as f: f.write(str(rmc_jar_path))
            print("    ✓ RMC provisioned successfully")
            patch_rmc_paths(primary_target, rmc_jar_path)
        else:
            print("    ⚠ RMC auto-download failed. Please install manually.")

    print("\n✅ Setup Complete!")
    print(f"  Primary Truth: {primary_target}")
    
    # Final cleanup if bootstrapped
    if 'tmp_dir' in locals(): shutil.rmtree(tmp_dir)
    return 0

if __name__ == "__main__":
    sys.exit(main())
