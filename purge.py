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
from pathlib import Path
from typing import List, Set

REPO_ROOT = Path(__file__).parent

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


def discover_owned_items() -> List[str]:
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
        for skill in skills_dir.iterdir():
            if skill.is_dir() and not skill.name.startswith("__"):
                owned.add(f"skills/{skill.name}")

    for skill_name in CORE_SKILLS:
        owned.add(f"skills/{skill_name}")

    return sorted(owned)

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
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"🚀 Initializing Surgical Purge (mode: {args.mode})")
    print("-----------------------------------------------")

    owned_items = discover_owned_items()
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
