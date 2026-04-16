#!/usr/bin/env python3
"""Pre-run RMC availability check and installation hook."""

import os
import sys
from pathlib import Path

# Import from scripts directory
sys.path.insert(0, str(Path(__file__).parent))
from download_rmc import download_rmc, is_valid_jar, probe_rmc_jar
from utils import safe_path

# Canonical path-marker filename written after a successful provision.
# Both the no-extension form and the .txt form are accepted on read so that
# files written by third-party tooling (e.g. Copilot) are still discovered.
_MARKER_NAMES = ("rmc_path", "rmc_path.txt")
_WRITE_MARKER_NAME = "rmc_path"  # always written without extension


def _read_marker(marker: Path) -> str | None:
    """Return the jar path recorded in *marker*, or None if unreadable."""
    try:
        return marker.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def resolve_rmc_destination() -> str:
    """
    Resolve rmc destination in priority order:
      1. RMC_DESTINATION env var (explicit override)
      2. .claude/rmc_path[.txt] marker in CWD (written by setup.py --mode local)
      3. ~/.claude/rmc_path[.txt] marker (written by setup.py --mode global)
      4. ~/.claude/rmc (fallback default)

    Both ``rmc_path`` and ``rmc_path.txt`` are probed so files written by
    third-party tooling are discovered regardless of the extension used.
    """
    if os.environ.get("RMC_DESTINATION"):
        return os.environ["RMC_DESTINATION"]

    search_bases = [Path.cwd() / ".claude", Path.home() / ".claude"]
    for base in search_bases:
        for name in _MARKER_NAMES:
            marker = base / name
            if marker.exists():
                jar_str = _read_marker(marker)
                if jar_str:
                    return str(Path(jar_str).parent)

    return str(Path.home() / ".claude" / "rmc")


def _write_rmc_path_marker(jar_path: Path) -> None:
    """Persist a canonical ``rmc_path`` marker alongside the jar."""
    marker = jar_path.parent / _WRITE_MARKER_NAME
    try:
        marker.write_text(str(jar_path), encoding="utf-8")
    except Exception as exc:
        # Non-fatal — the jar works even if the marker can't be written.
        print(f"[RMC Hook] Warning: could not write path marker: {exc}", file=sys.stderr)


def pre_run_rmc_check(rmc_destination: str | None = None) -> int:
    """
    Check if RMC is available and download if needed.

    Validation is two-stage:
      1. Magic-bytes check (is_valid_jar) — fast, detects truncated downloads.
      2. JVM probe (probe_rmc_jar) — runs ``java -jar`` briefly to catch
         "Invalid or corrupt jarfile" errors that pass the magic-bytes test.

    Returns:
        0: RMC available and JVM-loadable
        2: Download failed
    """
    if rmc_destination is None:
        rmc_destination = resolve_rmc_destination()

    dest_path = safe_path(rmc_destination)
    dest_path.mkdir(parents=True, exist_ok=True)
    jar_path = dest_path / "rmc.jar"

    # Stage 1: quick magic-bytes + size check
    if is_valid_jar(jar_path):
        jar_size = jar_path.stat().st_size
        if jar_size > 1_000_000:  # >1 MB
            # Stage 2: real JVM loadability probe
            if probe_rmc_jar(jar_path):
                print(f"[RMC Hook] rmc.jar valid at {jar_path} ({jar_size // 1024}KB)")
                _write_rmc_path_marker(jar_path)
                return 0
            else:
                print(
                    f"[RMC Hook] WARNING: rmc.jar at {jar_path} passes magic-bytes check "
                    "but is corrupt (JVM reports 'Invalid or corrupt jarfile'). "
                    "Removing and re-downloading.",
                    file=sys.stderr,
                )
                try:
                    jar_path.unlink()
                except Exception:
                    pass

    # No valid jar — download it
    print("[RMC Hook] rmc.jar not found or invalid, downloading...")

    result = download_rmc(
        url="https://github.com/rebeca-lang/org.rebecalang.rmc/releases/latest",
        dest_dir=str(dest_path),
    )

    if result == 0:
        print("[RMC Hook] Successfully provisioned rmc.jar")
        _write_rmc_path_marker(dest_path / "rmc.jar")
        return 0
    else:
        print("[RMC Hook] ERROR: Failed to download rmc.jar", file=sys.stderr)
        return 2


def main() -> None:
    sys.exit(pre_run_rmc_check())


if __name__ == "__main__":
    main()
