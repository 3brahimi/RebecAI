#!/usr/bin/env python3
"""
Surgical Purge Script for Claude Rebeca

1. Maintains a list of all files/folders possibly installed.
2. Removes them surgically if they exist.
3. Recursively removes parent folders ONLY if they become empty.
"""

import argparse
import os
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List, Set

REPO_ROOT = Path(__file__).parent
DEFAULT_REMOTE_OWNER = "3brahimi"
DEFAULT_REMOTE_REPO = "RebecAI"
DEFAULT_REMOTE_REF = "main"

# 1. Required core skills for fallback coverage
CORE_SKILLS = {
    "legata_to_rebeca",
    "rebeca_handbook",
    "rebeca_tooling",
    "rebeca_mutation",
    "rebeca_hallucination",
}

def lexists(path: Path) -> bool:
    return os.path.lexists(str(path))


def discover_owned_items_local() -> List[str]:
    """
    Discover removable project artifacts from repo truth.

    Includes:
      - all agents/*.md
      - corresponding .agent.md aliases (used by some targets)
      - compatibility aliases for hyphen/underscore renames
      - all skills/* directories (+ core fallback set)
      - rmc/tooling metadata
    """
    owned: Set[str] = {
        "rmc",
        "rmc_path",
        "configs",       # FSM runtime configuration files
        "docs",          # primary truth copy (used as source for .github/instructions symlink)
        "instructions",  # .github/instructions link
    }

    agents_dir = REPO_ROOT / "agents"
    if agents_dir.is_dir():
        for agent in agents_dir.glob("*.md"):
            owned.add(f"agents/{agent.name}")
            stem = agent.stem
            owned.add(f"agents/{stem}.agent.md")

            # Compatibility aliases so purge handles historical filename style flips.
            if "_" in stem:
                alt = stem.replace("_", "-")
                owned.add(f"agents/{alt}.md")
                owned.add(f"agents/{alt}.agent.md")
            if "-" in stem:
                alt = stem.replace("-", "_")
                owned.add(f"agents/{alt}.md")
                owned.add(f"agents/{alt}.agent.md")

    skills_dir = REPO_ROOT / "skills"
    if skills_dir.is_dir():
        for entry in skills_dir.iterdir():
            if entry.is_dir() and entry.name != "__pycache__":
                owned.add(f"skills/{entry.name}")
            elif entry.is_file():
                owned.add(f"skills/{entry.name}")

    # Files written by setup.py that have no source counterpart in the repo
    owned.add("skills/rmc_path.txt")

    for skill_name in CORE_SKILLS:
        owned.add(f"skills/{skill_name}")

    return sorted(owned)


def _build_owned_from_file_list(file_paths: List[str]) -> List[str]:
    """Build owned manifest entries from normalized repository-relative file paths."""
    owned: Set[str] = {
        "rmc",
        "rmc_path",
        "configs",
        "docs",
        "instructions",
    }

    agent_files = [p for p in file_paths if p.startswith("agents/") and p.endswith(".md")]
    for rel in agent_files:
        name = rel.split("/", 1)[1]
        if "/" in name:
            continue
        owned.add(f"agents/{name}")
        stem = Path(name).stem
        owned.add(f"agents/{stem}.agent.md")

        if "_" in stem:
            alt = stem.replace("_", "-")
            owned.add(f"agents/{alt}.md")
            owned.add(f"agents/{alt}.agent.md")
        if "-" in stem:
            alt = stem.replace("-", "_")
            owned.add(f"agents/{alt}.md")
            owned.add(f"agents/{alt}.agent.md")

    skill_entries: Set[str] = set()
    for rel in file_paths:
        if not rel.startswith("skills/"):
            continue
        rest = rel.split("/", 1)[1]
        if not rest:
            continue
        top = rest.split("/", 1)[0]
        if top and top != "__pycache__":
            skill_entries.add(top)

    for entry in skill_entries:
        owned.add(f"skills/{entry}")

    owned.add("skills/rmc_path.txt")
    for skill_name in CORE_SKILLS:
        owned.add(f"skills/{skill_name}")

    return sorted(owned)


def discover_owned_items_remote(owner: str, repo: str, ref: str, timeout: int = 8) -> List[str]:
    """Discover removable artifacts from a GitHub source zip snapshot."""
    archive_url = f"https://github.com/{owner}/{repo}/archive/{ref}.zip"

    try:
        with urllib.request.urlopen(archive_url, timeout=timeout) as response:
            with NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                tmp.write(response.read())
                zip_path = Path(tmp.name)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"remote-unavailable: {exc}") from exc

    try:
        file_paths: List[str] = []
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            if not names:
                raise RuntimeError("remote-empty-archive")

            prefix = names[0].split("/", 1)[0] + "/"
            for name in names:
                if not name.startswith(prefix):
                    continue
                rel = name[len(prefix):]
                if not rel or rel.endswith("/"):
                    continue
                file_paths.append(rel)

        return _build_owned_from_file_list(file_paths)
    except zipfile.BadZipFile as exc:
        raise RuntimeError("remote-invalid-zip") from exc
    finally:
        try:
            zip_path.unlink(missing_ok=True)
        except Exception:
            pass


def has_local_source_tree() -> bool:
    return (REPO_ROOT / "agents").is_dir() and (REPO_ROOT / "skills").is_dir()

def is_empty(path: Path) -> bool:
    """Check if a directory is empty (not counting .DS_Store)."""
    if not path.is_dir() or path.is_symlink():
        return False
    items = [i for i in os.listdir(path) if i != ".DS_Store"]
    return len(items) == 0

def remove_and_cleanup(path: Path, dry_run: bool):
    """Surgically remove an item and bubble up to clean empty parents."""
    if not lexists(path):
        return

    if dry_run:
        kind = "symlink" if path.is_symlink() else ("dir" if path.is_dir() else "file")
        print(f"  [dry-run] would remove {kind}: {path}")
        return

    # Record parent before deletion
    parent = path.parent

    # Delete the item
    try:
        if path.is_symlink():
            path.unlink()
            print(f"  ✓ Unlinked: {path}")
        elif path.is_dir():
            shutil.rmtree(path)
            print(f"  ✓ Removed dir: {path}")
        else:
            path.unlink()
            print(f"  ✓ Removed file: {path}")
    except Exception as e:
        print(f"  ✗ Failed to remove {path}: {e}")
        return

    # 3. Recursive parent cleanup
    # We only clean up parents that are part of the agent structures (.agents, .claude, etc.)
    # We stop bubbling up if we hit the user's home or the repo root.
    while parent and parent != Path.home() and parent != REPO_ROOT:
        if is_empty(parent):
            # If it's a root folder (.agents, .claude, .gemini), we only delete it if it's not a symlink
            # or if it's a dangling symlink.
            try:
                parent.rmdir()
                print(f"  ✓ Removed empty parent: {parent}")
                parent = parent.parent
            except OSError:
                break # Folder not empty or permission error
        else:
            break

def main():
    parser = argparse.ArgumentParser(description="Surgically purge project artifacts")
    parser.add_argument("--mode", choices=["local", "global", "both"], default="local")
    parser.add_argument("--source", choices=["auto", "local", "remote"], default="auto")
    parser.add_argument("--offline", action="store_true", help="Disable remote discovery and use local manifest building only")
    parser.add_argument("--owner", default=DEFAULT_REMOTE_OWNER, help="GitHub owner for remote manifest discovery")
    parser.add_argument("--repo", default=DEFAULT_REMOTE_REPO, help="GitHub repo for remote manifest discovery")
    parser.add_argument("--ref", default=DEFAULT_REMOTE_REF, help="GitHub ref (branch/tag/sha) for remote manifest discovery")
    parser.add_argument("--remote-timeout", type=int, default=8, help="Remote archive fetch timeout in seconds")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"🚀 Initializing Surgical Purge (mode: {args.mode})")
    print("-----------------------------------------------")

    local_tree = has_local_source_tree()
    discovery_source = "local"

    if args.source == "local":
        owned_items = discover_owned_items_local()
        discovery_source = "local"
    elif args.source == "remote":
        if args.offline:
            print("  ! Remote discovery requested but --offline is set; falling back to local discovery")
            owned_items = discover_owned_items_local()
            discovery_source = "local-fallback"
        else:
            owned_items = discover_owned_items_remote(args.owner, args.repo, args.ref, timeout=args.remote_timeout)
            discovery_source = "remote"
    else:
        # auto mode: prefer local source tree when present; otherwise try remote; if remote unavailable, fallback local.
        if local_tree:
            owned_items = discover_owned_items_local()
            discovery_source = "local"
        elif args.offline:
            owned_items = discover_owned_items_local()
            discovery_source = "local-offline"
        else:
            try:
                owned_items = discover_owned_items_remote(args.owner, args.repo, args.ref, timeout=args.remote_timeout)
                discovery_source = "remote-auto"
            except RuntimeError as exc:
                print(f"  ! Remote discovery unavailable ({exc}); falling back to local discovery")
                owned_items = discover_owned_items_local()
                discovery_source = "local-fallback"

    print(f"  Discovery source: {discovery_source}")
    print(f"  Discovered {len(owned_items)} owned artifact pattern(s)")

    # Define all potential roots to check
    roots = []
    if args.mode in ("local", "both"):
        roots.extend([
            REPO_ROOT / ".agents",
            REPO_ROOT / ".claude",
            REPO_ROOT / ".gemini",
            REPO_ROOT / ".github",
        ])
    if args.mode in ("global", "both"):
        roots.extend([
            Path.home() / ".agents",
            Path.home() / ".claude",
            Path.home() / ".gemini",
        ])

    # 2. Iterate through manifest and roots
    for root in roots:
        if not lexists(root):
            continue

        # Root special case: If the root itself is a symlink pointing to an .agents folder
        # we are purging, we don't delete the symlink UNLESS the target becomes empty.
        # However, the user's requirement is to check individual files.

        for item_rel in owned_items:
            target_path = root / item_rel
            if lexists(target_path):
                remove_and_cleanup(target_path, args.dry_run)

    # Final pass: Clean up roots if they became empty and are not our manifest items themselves
    for root in roots:
        if lexists(root) and is_empty(root):
            if not args.dry_run:
                root.rmdir()
                print(f"  ✓ Removed empty root: {root}")
            else:
                print(f"  [dry-run] would remove empty root: {root}")

        # Also clean up dangling symlinks for roots
        if lexists(root) and root.is_symlink():
            target = Path(os.readlink(str(root)))
            # If it was a relative link, make it absolute for checking
            if not target.is_absolute():
                target = (root.parent / target).resolve()

            if not lexists(target):
                if not args.dry_run:
                    root.unlink()
                    print(f"  ✓ Removed dangling symlink root: {root}")
                else:
                    print(f"  [dry-run] would remove dangling symlink root: {root}")

    print("\nPurge complete.")

if __name__ == "__main__":
    main()
