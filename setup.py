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
GITHUB_REPO = "3brahimi/RebecAI"
ZIP_URL = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/main.zip"


def _zip_url(commit: str | None) -> str:
    if commit:
        return f"https://github.com/{GITHUB_REPO}/archive/{commit}.zip"
    return ZIP_URL
RMC_LATEST_URL = "https://github.com/rebeca-lang/org.rebecalang.rmc/releases/latest"

# Coordinator/sub-agent design contract
REQUIRED_SKILLS: Set[str] = {
    "legata_to_rebeca",
    "rebeca_tooling",
    "rebeca_handbook",
    "rebeca_mutation",
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

# --- STANDALONE UTILITIES ---

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
    """Parse @agent_name mentions from coordinator markdown.

    Only collects refs from lines whose entire content is @name tokens
    (the explicit subagent listing line).  Prose lines that contain a
    single @name alongside other words are ignored to prevent false
    positives from placeholder text like 'the mapped @sub_agent'.
    """
    refs: Set[str] = set()
    for line in coordinator_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        tokens = stripped.split()
        if all(re.match(r"^@[A-Za-z0-9_]+$", tok) for tok in tokens):
            for tok in tokens:
                refs.add(tok[1:])  # strip leading @
    return {f"{name}.md" for name in refs}


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

# Keys that Gemini CLI's local sub-agent loader does not recognise and will
# reject with a "Validation failed: Unrecognized key(s)" error.
# _GEMINI_UNSUPPORTED_KEYS = {"version", "user-invocable", "schema", "skills"}
_GEMINI_UNSUPPORTED_KEYS = {"version", "user-invocable", "schema"}

def _write_gemini_agent(src: Path, dest: Path) -> None:
    """Copy an agent .md file to dest, stripping Gemini-incompatible frontmatter keys."""
    import re as _re
    text = src.read_text()
    # Split on the closing --- of the frontmatter block
    fm_match = _re.match(r'^---\n(.*?\n)---\n(.*)', text, _re.DOTALL)
    if not fm_match:
        dest.write_text(text)
        return
    fm_body, rest = fm_match.group(1), fm_match.group(2)
    # Strip lines whose key is in the unsupported set
    # Handles simple scalar ("key: value") and block scalars ("key: |\n  ...")
    filtered_lines: list[str] = []
    skip_indent = False
    for line in fm_body.splitlines(keepends=True):
        key_match = _re.match(r'^([a-zA-Z][a-zA-Z0-9_-]*):', line)
        if key_match:
            skip_indent = key_match.group(1) in _GEMINI_UNSUPPORTED_KEYS
        elif line[:1] in (' ', '\t'):
            pass  # continuation of previous key — honour skip_indent
        else:
            skip_indent = False
        if not skip_indent:
            filtered_lines.append(line)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(f"---\n{''.join(filtered_lines)}---\n{rest}")
    print(f"  ✓ Copied (gemini-clean): {dest}")


def link_to_target(target_root: Path, primary_truth: Path, owned_skills: set[str], is_github: bool = False):
    if not target_root: return
    is_gemini = target_root.name == ".gemini" or target_root.parent.name == ".gemini"
    print(f"  Linking to {target_root}...")

    if target_root.is_symlink(): target_root.unlink()
    target_root.mkdir(parents=True, exist_ok=True)

    # 1. Agents
    agents_dest = target_root / "agents"
    agents_dest.mkdir(parents=True, exist_ok=True)
    for agent in (primary_truth / "agents").glob("*.md"):
        link_name = agent.name if not is_github else agent.stem + ".agent.md"
        dest = agents_dest / link_name
        if is_gemini:
            # Gemini CLI may not follow symlinks and rejects unknown frontmatter keys —
            # write a physical copy with incompatible keys stripped.
            if dest.is_symlink() or dest.exists():
                dest.unlink() if dest.is_symlink() else dest.unlink()
            _write_gemini_agent(agent, dest)
        else:
            create_surgical_symlink(agent, dest)

    # 2. Skills — only skills this repo owns, never third-party skills
    for skill in (primary_truth / "skills").iterdir():
        if skill.name == "__pycache__":
            continue
        if skill.name not in owned_skills:
            continue
        if skill.is_dir():
            create_surgical_symlink(skill, target_root / "skills" / skill.name)
        elif skill.is_file():
            create_surgical_symlink(skill, target_root / "skills" / skill.name)


def patch_agent_placeholders(
    target_root: Path,
    scripts_path: Path,
    jar_path: Path,
    install_root: Path = None,
) -> None:
    """
    Replace <install_root>, <scripts>, <jar>, <agents>, and <skills> placeholders
    in installed agent and skill markdown files with absolute paths resolved at
    install time.

    Placeholders:
      <install_root> — primary installation root
      <scripts>      — rebeca_tooling/scripts directory
      <jar>          — rmc.jar file
      <agents>       — agents directory (<install_root>/agents)
      <skills>       — skills directory (<install_root>/skills)

    install_root overrides target_root for the <install_root> replacement only.
    Use this for Gemini: scripts live under .gemini/skills/ but <install_root>
    must still point to the primary truth (.agents/) where RMC jar resides.

    Rewrites files under target_root/agents/ and target_root/skills/ — never
    touches Python source.
    """
    effective_root = install_root if install_root is not None else target_root
    print(f"  Patching agent placeholders in {target_root} with install_root={effective_root}, scripts={scripts_path}, jar={jar_path}...")
    root_str = str(effective_root.absolute())
    scripts_str = str(scripts_path.absolute())
    jar_str = str(jar_path.absolute())
    agents_str = str((effective_root / "agents").absolute())
    skills_str = str((effective_root / "skills").absolute())

    # Process both agents/ and skills/ directories
    for base_dir in [target_root / "agents", target_root / "skills"]:
        if not base_dir.is_dir():
            continue

        for f in base_dir.rglob("*.md"):
            try:
                content = f.read_text(encoding="utf-8")
                new_content = (content
                    .replace("<install_root>", root_str)
                    .replace("<scripts>", scripts_str)
                    .replace("<jar>", jar_str)
                    .replace("<agents>", agents_str)
                    .replace("<skills>", skills_str))
                if new_content != content:
                    f.write_text(new_content, encoding="utf-8")
            except Exception:
                pass


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
    parser.add_argument("--commit", help="Git commit hash or branch to install (default: main)")
    parser.add_argument("--rmc-tag", help="Optional RMC release tag (e.g., v2.13)")
    parser.add_argument("--no-rmc", action="store_true")
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Validate repo-local installer invariants without writing files. "
            "Exits 0 on success, non-zero on failure."
        ),
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be installed without writing anything")
    args = parser.parse_args()

    if args.check:
        local_src = Path(__file__).parent
        if not (local_src / "agents").is_dir() or not (local_src / "skills").is_dir():
            print("✗ --check requires repo-local layout (missing agents/ or skills/ next to setup.py)")
            return 2

        ok, msgs = validate_design_coverage(local_src, strict=True)
        for msg in msgs:
            prefix = "✓" if ok else "✗"
            print(f"{prefix} {msg}")
        if not ok:
            return 1

        # Minimal runtime config expected by workflow_fsm.py
        cfg = local_src / "configs" / "rmc_defaults.json"
        if not cfg.exists():
            print(f"✗ Missing required config: {cfg}")
            return 1

        print("✓ Installer self-check passed")
        return 0

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
        print(f"  commit      : {args.commit or 'main (latest)'}")
        print(f"  mode        : {args.mode}")
        print(f"  rmc-tag     : {args.rmc_tag or 'latest'}")
        print(f"  no-rmc      : {args.no_rmc}")
        print()

        print(f"[1] Primary installation target: {primary_target}")
        if src_root:
            agents = sorted((src_root / "agents").glob("*.md"))
            skills = sorted(p for p in (src_root / "skills").iterdir() if p.is_dir() and p.name != "__pycache__")

            print(f"  agents/  ({len(agents)} files)")
            for a in agents:
                print(f"    {primary_target / 'agents' / a.name}")

            print(f"  skills/  ({len(skills)} directories)")
            for s in skills:
                print(f"    {primary_target / 'skills' / s.name}/")

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
        if not download_file(_zip_url(args.commit), zip_path): return 1

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

    # agents/ is fully owned — safe to replace wholesale
    for sub in ("agents",):
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

    # configs/ — FSM-required runtime configuration (minimum: rmc_defaults.json)
    configs_src = src_root / "configs"
    if configs_src.exists():
        configs_dest = primary_target / "configs"
        configs_dest.mkdir(parents=True, exist_ok=True)
        n_copied = 0
        for entry in configs_src.iterdir():
            if entry.is_file():
                shutil.copy2(entry, configs_dest / entry.name)
                n_copied += 1
        print(f"    ✓ Installed configs/ ({n_copied} file(s))")
    else:
        print("    ⚠ configs/ not found in source — FSM budget enforcement will use hardcoded defaults")

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

    # Stamp resolved <scripts> and <jar> into agent markdown files so the agent
    # receives concrete paths at runtime — no filesystem probing required.
    scripts_path = primary_target / "skills" / "rebeca_tooling" / "scripts"
    jar_for_patch = rmc_jar_path if rmc_jar_path else (primary_target / "rmc" / "rmc.jar")
    patch_agent_placeholders(primary_target, scripts_path, jar_for_patch)
    print(f"  ✓ Agent paths stamped: scripts={scripts_path}, jar={jar_for_patch}")

    # Gemini installs physical copies that cannot follow symlinks back to the
    # patched primary truth — patch them separately using Gemini-rooted paths
    # for <scripts> but primary_target paths for <install_root>, <agents>, <skills>.
    # Skills are symlinked under .gemini/skills/ so Python resolves them fine.
    # RMC jar lives only under primary_target/rmc/ — reuse that path.
    if not args.target_root:
        gemini_root = GEMINI_ROOT_LOCAL if args.mode == "local" else GEMINI_ROOT_GLOBAL
        gemini_scripts = gemini_root / "skills" / "rebeca_tooling" / "scripts"
        patch_agent_placeholders(gemini_root, gemini_scripts, jar_for_patch)
        print(f"  ✓ Gemini agent paths stamped: {gemini_root / 'agents'}")

    print("\n✅ Setup Complete!")
    print(f"  Primary Truth: {primary_target}")

    # Final cleanup if bootstrapped
    if 'tmp_dir' in locals(): shutil.rmtree(tmp_dir)
    return 0

if __name__ == "__main__":
    sys.exit(main())
