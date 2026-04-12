#!/usr/bin/env python3
"""
Claude Rebeca Purge Script

Removes installed agents, skills, RMC jar, and the rmc_path marker
from a local (.claude/ in CWD) or global (~/.claude/) installation.

Usage:
  python3 purge.py                  # purge local install (.claude/ in CWD)
  python3 purge.py --mode global    # purge global install (~/.claude/)
  python3 purge.py --target-root /path/to/install  # purge custom location
  python3 purge.py --what agents    # remove only agents
  python3 purge.py --what skills    # remove only skills
  python3 purge.py --what rmc       # remove only rmc jar + marker
  python3 purge.py --what all       # remove everything (default)

Returns:
    0: Success
    1: Nothing to remove (target does not exist)
    2: Partial failure (some items could not be removed)
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "rebeca-tooling" / "lib"))

from utils import safe_path

LOCAL_TARGET = Path.cwd() / ".claude"
GLOBAL_TARGET = Path.home() / ".claude"


def remove(path: Path, label: str, dry_run: bool) -> bool:
    """Remove a file or directory. Returns True on success."""
    if not path.exists():
        print(f"  - {label}: not present, skipping")
        return True
    if dry_run:
        kind = "dir" if path.is_dir() else "file"
        print(f"  [dry-run] would remove {kind}: {path}")
        return True
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        print(f"  ✓ Removed {label}: {path}")
        return True
    except Exception as e:
        print(f"  ✗ Failed to remove {label}: {e}", file=sys.stderr)
        return False


def purge(target_root: str, what: str = "all", dry_run: bool = False) -> int:
    target_path = safe_path(target_root)

    if not target_path.exists():
        print(f"Nothing to purge — {target_path} does not exist.")
        return 1

    print(f"{'[dry-run] ' if dry_run else ''}Purging from: {target_path}")
    print()

    failures = 0

    # Discover installed agents from repo so we only remove what we own
    agents_dir = REPO_ROOT / "agents"
    known_agents = [f.name for f in agents_dir.glob("*.md")] if agents_dir.exists() else []

    # Discover installed skills from repo so we only remove what we own
    skills_dir = REPO_ROOT / "skills"
    known_skills = [
        d.name for d in skills_dir.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    ] if skills_dir.exists() else []

    if what in ("agents", "all"):
        print("Removing agents:")
        if known_agents:
            for name in known_agents:
                if not remove(target_path / "agents" / name, f"agent/{name}", dry_run):
                    failures += 1
            # Remove agents dir if now empty
            agents_dest = target_path / "agents"
            if not dry_run and agents_dest.exists() and not any(agents_dest.iterdir()):
                agents_dest.rmdir()
                print(f"  ✓ Removed empty agents/ directory")
        else:
            print("  - no agents discovered in repo")
        print()

    if what in ("skills", "all"):
        print("Removing skills:")
        if known_skills:
            for name in known_skills:
                if not remove(target_path / "skills" / name, f"skill/{name}", dry_run):
                    failures += 1
            # Remove skills dir if now empty
            skills_dest = target_path / "skills"
            if not dry_run and skills_dest.exists() and not any(skills_dest.iterdir()):
                skills_dest.rmdir()
                print(f"  ✓ Removed empty skills/ directory")
        else:
            print("  - no skills discovered in repo")
        print()

    if what in ("rmc", "all"):
        print("Removing RMC:")
        if not remove(target_path / "rmc", "rmc/", dry_run):
            failures += 1
        if not remove(target_path / "rmc_path", "rmc_path marker", dry_run):
            failures += 1
        print()

    if failures > 0:
        print(f"Purge completed with {failures} failure(s).")
        return 2

    print("Purge complete.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Purge installed Claude Rebeca agents, skills, and RMC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Purge local install (.claude/ in CWD)
  python3 purge.py

  # Purge global install (~/.claude/)
  python3 purge.py --mode global

  # Preview what would be removed without deleting
  python3 purge.py --dry-run

  # Remove only the RMC jar
  python3 purge.py --what rmc

  # Remove only agents from global install
  python3 purge.py --mode global --what agents
        """
    )
    parser.add_argument(
        "--mode",
        choices=["local", "global"],
        default="local",
        help="Install mode to purge: local (.claude/ in CWD) or global (~/.claude/). Default: local"
    )
    parser.add_argument(
        "--target-root",
        default=None,
        help="Override target directory (overrides --mode)"
    )
    parser.add_argument(
        "--what",
        choices=["agents", "skills", "rmc", "all"],
        default="all",
        help="What to remove. Default: all"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be removed without deleting anything"
    )

    args = parser.parse_args()

    if args.target_root:
        target_root = args.target_root
    elif os.environ.get("CLAUDE_INSTALL_DIR"):
        target_root = os.environ["CLAUDE_INSTALL_DIR"]
    elif args.mode == "global":
        target_root = str(GLOBAL_TARGET)
    else:
        target_root = str(LOCAL_TARGET)

    sys.exit(purge(target_root, args.what, args.dry_run))


if __name__ == "__main__":
    main()
