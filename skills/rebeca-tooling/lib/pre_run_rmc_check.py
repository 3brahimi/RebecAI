#!/usr/bin/env python3
"""Pre-run RMC availability check and installation hook."""

import os
import sys
from pathlib import Path

# Import from lib directory
sys.path.insert(0, str(Path(__file__).parent))
from download_rmc import download_rmc, is_valid_jar
from utils import safe_path


def resolve_rmc_destination() -> str:
    """
    Resolve rmc destination in priority order:
      1. RMC_DESTINATION env var (explicit override)
      2. .claude/rmc_path marker in CWD (written by setup.py --mode local)
      3. ~/.claude/rmc_path marker (written by setup.py --mode global)
      4. ~/.claude/rmc (fallback default)
    """
    if os.environ.get("RMC_DESTINATION"):
        return os.environ["RMC_DESTINATION"]

    for marker in [Path.cwd() / ".claude" / "rmc_path",
                   Path.home() / ".claude" / "rmc_path"]:
        if marker.exists():
            rmc_jar = marker.read_text().strip()
            return str(Path(rmc_jar).parent)

    return str(Path.home() / ".claude" / "rmc")


def pre_run_rmc_check(rmc_destination: str | None = None) -> int:
    """
    Check if RMC is available and download if needed.

    Returns:
        0: RMC available
        2: Download failed
    """
    if rmc_destination is None:
        rmc_destination = resolve_rmc_destination()

    dest_path = safe_path(rmc_destination)
    dest_path.mkdir(parents=True, exist_ok=True)
    jar_path = dest_path / "rmc.jar"

    # Check if valid rmc.jar exists
    if is_valid_jar(jar_path):
        jar_size = jar_path.stat().st_size
        if jar_size > 1_000_000:  # >1MB
            print(f"[RMC Hook] rmc.jar valid at {jar_path} ({jar_size // 1024}KB)")
            return 0

    # No valid jar - download it
    print("[RMC Hook] rmc.jar not found or invalid, downloading...")

    result = download_rmc(
        url="https://github.com/rebeca-lang/org.rebecalang.rmc/releases/latest",
        dest_dir=str(dest_path)
    )

    if result == 0:
        print("[RMC Hook] Successfully provisioned rmc.jar")
        return 0
    else:
        print("[RMC Hook] ERROR: Failed to download rmc.jar", file=sys.stderr)
        return 2


def main():
    sys.exit(pre_run_rmc_check())


if __name__ == "__main__":
    main()
