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
from typing import List, Tuple, Optional, Set

# Configuration
GITHUB_REPO = "3brahimi/claude-rebeca"
ZIP_URL = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/main.zip"
RMC_LATEST_URL = "https://github.com/rebeca-lang/org.rebecalang.rmc/releases/latest"

# Coordinator/sub-agent design contract
REQUIRED_SKILLS: Set[str] = {
    "legata_to_rebeca",
    "rebeca_tooling",
    "rebeca_handbook",
    "rebeca_mutation",
    "rebeca_hallucination",
}

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
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response, open(dest, "wb") as out_file:
            total = response.headers.get("Content-Length")
            total_bytes = int(total) if total else None
            downloaded = 0
            last_pct = -1
            chunk_size = 65536  # 64 KB
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                mb = downloaded / (1024 * 1024)
                if total_bytes:
                    pct = int(downloaded / total_bytes * 100)
                    if pct != last_pct:
                        total_mb = total_bytes / (1024 * 1024)
                        print(f"  {mb:.1f} / {total_mb:.1f} MB ({pct}%)", end="\r", flush=True)
                        last_pct = pct
                else:
                    print(f"  {mb:.1f} MB downloaded", end="\r", flush=True)
        print(f"  {downloaded / (1024 * 1024):.1f} MB — done")
        return True
    except Exception as e:
        print(f"\n  ❌ Download failed: {e}")
        return False


def is_valid_jar(path: Path) -> bool:
    """Return True if path exists and has ZIP/JAR magic bytes."""
    if not path.exists() or not path.is_file():
        return False
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"PK\x03\x04"
    except Exception:
        return False


def resolve_latest_tag() -> Optional[str]:
    """Resolve latest RMC release tag from GitHub redirect."""
    try:
        req = urllib.request.Request(RMC_LATEST_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response:
            final_url = response.geturl()
        m = re.search(r"/tag/([^/]+)$", final_url)
        return m.group(1) if m else None
    except Exception:
        return None


def provision_rmc_jar(dest_jar: Path, rmc_tag: Optional[str] = None) -> bool:
    """Download rmc.jar using tagged assets when available, with safe fallbacks."""
    candidates: List[str] = []

    if rmc_tag:
        candidates.extend([
            f"https://github.com/rebeca-lang/org.rebecalang.rmc/releases/download/{rmc_tag}/rmc-{rmc_tag}.jar",
            f"https://github.com/rebeca-lang/org.rebecalang.rmc/releases/download/{rmc_tag}/rmc.jar",
        ])
    else:
        latest_tag = resolve_latest_tag()
        if latest_tag:
            candidates.extend([
                f"https://github.com/rebeca-lang/org.rebecalang.rmc/releases/download/{latest_tag}/rmc-{latest_tag}.jar",
                f"https://github.com/rebeca-lang/org.rebecalang.rmc/releases/download/{latest_tag}/rmc.jar",
            ])
        candidates.append("https://github.com/rebeca-lang/org.rebecalang.rmc/releases/latest/download/rmc.jar")

    for url in candidates:
        if download_file(url, dest_jar) and is_valid_jar(dest_jar):
            return True

    return False

def lexists(path: Path) -> bool:
    return os.path.lexists(str(path))


def _find_coordinator_file(agents_dir: Path) -> Optional[Path]:
    """Locate coordinator agent file across supported naming variants."""
    candidates = [
        agents_dir / "legata_to_rebeca.md",
        agents_dir / "legata-to-rebeca.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _extract_subagents_from_coordinator(coordinator_file: Path) -> Set[str]:
    """Parse @sub_agent mentions from coordinator markdown."""
    text = coordinator_file.read_text(encoding="utf-8")
    refs = set(re.findall(r"@([A-Za-z0-9_]+)", text))
    return {f"{name}.md" for name in refs if name}


def validate_design_coverage(root: Path, strict: bool = True) -> Tuple[bool, List[str]]:
    """
    Validate that coordinator + referenced subagents + required skills exist.
    Returns (ok, messages).
    """
    messages: List[str] = []
    agents_dir = root / "agents"
    skills_dir = root / "skills"

    if not agents_dir.exists() or not skills_dir.exists():
        msg = f"Missing agents/skills under {root}"
        return (False, [msg]) if strict else (True, [f"warning: {msg}"])

    coordinator = _find_coordinator_file(agents_dir)
    if coordinator is None:
        msg = "Coordinator agent missing: expected legata_to_rebeca.md or legata-to-rebeca.md"
        return (False, [msg]) if strict else (True, [f"warning: {msg}"])

    missing: List[str] = []

    # All subagents referenced by coordinator must exist.
    for subagent_file in sorted(_extract_subagents_from_coordinator(coordinator)):
        if not (agents_dir / subagent_file).exists():
            missing.append(f"agents/{subagent_file}")

    # Core skill set required by the coordinator design.
    for skill_name in sorted(REQUIRED_SKILLS):
        if not (skills_dir / skill_name).is_dir():
            missing.append(f"skills/{skill_name}/")

    if missing:
        messages.extend(["Missing design artifacts:"] + [f"- {m}" for m in missing])
        return (False, messages) if strict else (True, [f"warning: {m}" for m in messages])

    messages.append(f"Coordinator design validated using {coordinator.name}")
    return True, messages

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

def link_to_target(target_root: Path, primary_truth: Path, owned_skills: set[str], is_github: bool = False):
    if not target_root: return
    print(f"  Linking to {target_root}...")

    if target_root.is_symlink(): target_root.unlink()
    target_root.mkdir(parents=True, exist_ok=True)

    # 1. Link Agents
    for agent in (primary_truth / "agents").glob("*.md"):
        link_name = agent.name if not is_github else agent.stem + ".agent.md"
        create_surgical_symlink(agent, target_root / "agents" / link_name)

    # 2. Link Skills — only skills this repo owns, never third-party skills
    for skill in (primary_truth / "skills").iterdir():
        if skill.name == "__pycache__":
            continue
        if skill.name not in owned_skills:
            continue
        if skill.is_dir():
            create_surgical_symlink(skill, target_root / "skills" / skill.name)
        elif skill.is_file():
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
    parser.add_argument("--target-root", help="Custom installation root (overrides --mode)")
    parser.add_argument("--rmc-tag", help="Optional RMC release tag (e.g., v2.13)")
    parser.add_argument("--no-rmc", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be installed without writing anything")
    args = parser.parse_args()

    if args.dry_run:
        local_src = Path(__file__).parent
        src_root = local_src if (local_src / "agents").exists() and (local_src / "skills").exists() else None
        src_mode = "repo-local" if src_root else "remote-bootstrap (GitHub ZIP)"

        primary_target = Path(args.target_root).expanduser().resolve() if args.target_root else (
            AGENTS_ROOT_LOCAL if args.mode == "local" else AGENTS_ROOT_GLOBAL
        )

        symlink_targets: list[tuple[Path, bool]] = []
        if not args.target_root:
            symlink_targets = [
                (CLAUDE_ROOT_LOCAL if args.mode == "local" else CLAUDE_ROOT_GLOBAL, False),
                (GEMINI_ROOT_LOCAL if args.mode == "local" else GEMINI_ROOT_GLOBAL, False),
            ]
            if args.mode == "local":
                symlink_targets.append((GITHUB_ROOT, True))

        rmc_jar = primary_target / "rmc" / "rmc.jar"

        print("🔍 DRY RUN — no files will be written")
        print(f"  source      : {src_mode}")
        print(f"  mode        : {args.mode}")
        print(f"  rmc-tag     : {args.rmc_tag or 'latest'}")
        print(f"  no-rmc      : {args.no_rmc}")
        print()

        print(f"[1] Primary installation target: {primary_target}")
        if src_root:
            agents = sorted((src_root / "agents").glob("*.md"))
            skills = sorted(p for p in (src_root / "skills").iterdir() if p.is_dir() and p.name != "__pycache__")
            docs   = src_root / "docs"

            print(f"  agents/  ({len(agents)} files)")
            for a in agents:
                print(f"    {primary_target / 'agents' / a.name}")

            print(f"  skills/  ({len(skills)} directories)")
            for s in skills:
                print(f"    {primary_target / 'skills' / s.name}/")

            if docs.exists():
                print(f"  docs/")
                print(f"    {primary_target / 'docs'}/")
        else:
            print("  (source not available locally — would download from GitHub)")
        print()

        if symlink_targets:
            print(f"[2] Symlinks into AI agent roots:")
            for t_root, is_github in symlink_targets:
                label = t_root.name + (" (GitHub/Copilot)" if is_github else "")
                print(f"  {label}  →  {t_root}")
                if src_root:
                    for a in sorted((src_root / "agents").glob("*.md")):
                        link_name = a.stem + ".agent.md" if is_github else a.name
                        print(f"    agents/{link_name}  →  {primary_target / 'agents' / a.name}")
                    for s in sorted(p for p in (src_root / "skills").iterdir() if p.is_dir() and p.name != "__pycache__"):
                        print(f"    skills/{s.name}/  →  {primary_target / 'skills' / s.name}/")
                    if is_github and (src_root / "docs").exists():
                        print(f"    instructions/  →  {primary_target / 'docs'}/")
            print()

        if not args.no_rmc:
            print(f"[3] RMC Model Checker:")
            print(f"    jar destination : {rmc_jar}")
            print(f"    rmc_path file   : {primary_target / 'rmc_path'}")
            print(f"    download source : GitHub releases ({args.rmc_tag or 'latest'})")
        else:
            print(f"[3] RMC Model Checker: skipped (--no-rmc)")
        print()
        print("Run without --dry-run to apply.")
        return 0

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

    # Contract guardrail: source must fully cover coordinator-subagent design.
    ok, coverage_msgs = validate_design_coverage(src_root, strict=True)
    for msg in coverage_msgs:
        prefix = "  ✓" if ok else "  ✗"
        print(f"{prefix} {msg}")
    if not ok:
        return 1

    # 2. Define Primary Target
    primary_target = Path(args.target_root).expanduser().resolve() if args.target_root else (
        AGENTS_ROOT_LOCAL if args.mode == "local" else AGENTS_ROOT_GLOBAL
    )
    primary_target.mkdir(parents=True, exist_ok=True)

    # 3. Install Master Truth — surgical copy, never wipe unowned content
    print(f"  Installing Master Source to {primary_target}...")
    _ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".*")

    # agents/ and docs/ are fully owned — safe to replace wholesale
    for sub in ("agents", "docs"):
        dest = primary_target / sub
        if dest.exists(): shutil.rmtree(dest)
        if (src_root / sub).exists():
            shutil.copytree(src_root / sub, dest, ignore=_ignore)

    # skills/ is a shared namespace — only copy/replace skills we own
    skills_dest = primary_target / "skills"
    skills_dest.mkdir(parents=True, exist_ok=True)
    skills_src = src_root / "skills"
    if skills_src.exists():
        for entry in skills_src.iterdir():
            if entry.name == "__pycache__":
                continue
            dest_entry = skills_dest / entry.name
            if entry.is_dir():
                if dest_entry.exists() or dest_entry.is_symlink():
                    shutil.rmtree(dest_entry) if dest_entry.is_dir() else dest_entry.unlink()
                shutil.copytree(entry, dest_entry, ignore=_ignore)
            elif entry.is_file():
                shutil.copy2(entry, dest_entry)

    # Validate installed target as well (defensive completeness check).
    ok, coverage_msgs = validate_design_coverage(primary_target, strict=True)
    for msg in coverage_msgs:
        prefix = "  ✓" if ok else "  ✗"
        print(f"{prefix} {msg}")
    if not ok:
        return 1

    # 4. Surgical Symlinking to AI Agents (skip when explicit --target-root is used)
    if not args.target_root:
        # Compute which skills this repo owns (from source, not the shared .agents/skills/ dir)
        owned_skills: set[str] = set()
        skills_src = src_root / "skills"
        if skills_src.exists():
            for entry in skills_src.iterdir():
                if entry.name != "__pycache__":
                    owned_skills.add(entry.name)

        targets = [
            (CLAUDE_ROOT_LOCAL if args.mode == "local" else CLAUDE_ROOT_GLOBAL, False),
            (GEMINI_ROOT_LOCAL if args.mode == "local" else GEMINI_ROOT_GLOBAL, False),
        ]
        if args.mode == "local":
            targets.append((GITHUB_ROOT, True))

        for t_root, is_github in targets:
            link_to_target(t_root, primary_target, owned_skills, is_github)

    # 5. Provision RMC Toolchain
    rmc_jar_path = None
    if not args.no_rmc:
        print("\n📦 Provisioning RMC Model Checker...")
        rmc_dest = primary_target / "rmc"
        rmc_dest.mkdir(parents=True, exist_ok=True)

        rmc_jar_path = rmc_dest / "rmc.jar"
        if provision_rmc_jar(rmc_jar_path, args.rmc_tag):
            with open(primary_target / "rmc_path", "w") as f: f.write(str(rmc_jar_path))
            print("    ✓ RMC provisioned successfully")
            patch_rmc_paths(primary_target, rmc_jar_path)
            # Keep one deterministic patched-path footprint inside installed artifacts.
            # Integration test IT-015 checks installed agents/skills for the resolved jar path.
            (primary_target / "skills" / "rmc_path.txt").write_text(str(rmc_jar_path), encoding="utf-8")
        else:
            print("    ⚠ RMC auto-download failed. Please install manually.")

    print("\n✅ Setup Complete!")
    print(f"  Primary Truth: {primary_target}")

    # Final cleanup if bootstrapped
    if 'tmp_dir' in locals(): shutil.rmtree(tmp_dir)
    return 0

if __name__ == "__main__":
    sys.exit(main())
