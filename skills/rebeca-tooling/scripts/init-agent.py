#!/usr/bin/env python3
"""
init-agent (WF-01): Toolchain and Inputs Initialization

Validates inputs, provisions RMC, pins toolchain metadata, and captures a
golden snapshot. Emits a JSON contract consumed by coordinator shared_state.step01.

Exit codes:
  0: Success — full contract written to stdout
  1: Failure — error envelope written to stdout
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Bootstrap: add skills scripts to path before importing
# ---------------------------------------------------------------------------
_SCRIPTS = Path(__file__).parent.parent / "skills" / "rebeca-tooling" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from pre_run_rmc_check import pre_run_rmc_check, resolve_rmc_destination  # noqa: E402
from snapshotter import capture_snapshot  # noqa: E402
from utils import safe_path  # noqa: E402


# ---------------------------------------------------------------------------
# Error Envelope — canonical failure format for all sub-agents
# ---------------------------------------------------------------------------

def _error(phase: str, agent: str, message: str) -> Dict[str, Any]:
    """Return a canonical Error Envelope dict."""
    return {
        "status": "error",
        "phase": phase,
        "agent": agent,
        "message": message,
    }


# ---------------------------------------------------------------------------
# Path validation wrapper
# ---------------------------------------------------------------------------

def _checked_safe_path(p: str, label: str) -> Tuple[Optional[Path], Optional[str]]:
    """
    Call safe_path(p) and return (path, None) on success or (None, error_msg)
    if safe_path calls sys.exit due to a path-traversal violation.
    """
    try:
        return safe_path(p), None
    except SystemExit:
        return None, f"{label} path escapes allowed base (~): {p}"
    except Exception as exc:
        return None, f"{label} path error: {exc}"


# ---------------------------------------------------------------------------
# RMC version detection
# ---------------------------------------------------------------------------

def _detect_rmc_version(jar_path: Path) -> str:
    """
    Probe RMC jar for a version string.

    Strategy:
      1. Run `java -jar <jar>` with a 5 s timeout; take the first non-empty
         output line (RMC prints usage/version on bare invocation).
      2. Fall back to the jar filename stem if it encodes a version tag
         (e.g. 'rmc-2.15.0' → '2.15.0').
      3. Return 'unknown' as last resort.
    """
    try:
        proc = subprocess.run(
            ["java", "-jar", str(jar_path)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        combined = proc.stdout + proc.stderr
        for line in combined.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:120]
    except Exception:
        pass

    stem = jar_path.stem  # e.g. "rmc-2.15.0" or "rmc"
    if "-" in stem:
        return stem.split("-", 1)[1]
    return "unknown"


# ---------------------------------------------------------------------------
# Python environment metadata
# ---------------------------------------------------------------------------

def _python_env() -> Dict[str, str]:
    return {
        "version": sys.version,
        "executable": sys.executable,
    }


# ---------------------------------------------------------------------------
# Core init logic
# ---------------------------------------------------------------------------

def run_init(
    source_file_path: str,
    model: str,
    prop: str,
    snapshot_out: str,
    rmc_destination: Optional[str],
) -> Tuple[Dict[str, Any], int]:
    """
    Execute WF-01 initialization steps.

    Returns (output_dict, exit_code) where exit_code is 0 on success, 1 on
    any failure. output_dict is either a success contract or an Error Envelope.
    """
    # 1. Validate input file paths
    model_path, err = _checked_safe_path(model, "model")
    if err:
        return _error("step01", "init-agent", f"Invalid path: {err}"), 1

    prop_path, err = _checked_safe_path(prop, "property")
    if err:
        return _error("step01", "init-agent", f"Invalid path: {err}"), 1

    assert model_path is not None and prop_path is not None  # satisfied by err check above

    if not model_path.exists():
        return _error("step01", "init-agent", f"Model file not found: {model}"), 1
    if not prop_path.exists():
        return _error("step01", "init-agent", f"Property file not found: {prop}"), 1

    # 2. Provision RMC (downloads if missing)
    rc = pre_run_rmc_check(rmc_destination)
    if rc != 0:
        return _error(
            "step01",
            "init-agent",
            f"pre_run_rmc_check failed (exit {rc}): RMC unavailable or download failed",
        ), 1

    # 3. Detect RMC version and Python environment
    dest_dir = rmc_destination if rmc_destination else resolve_rmc_destination()
    dest_path, err = _checked_safe_path(dest_dir, "rmc_destination")
    if err:
        return _error("step01", "init-agent", f"Invalid rmc_destination path: {err}"), 1

    assert dest_path is not None
    jar_path = dest_path / "rmc.jar"
    rmc_version = _detect_rmc_version(jar_path)

    # 4. Capture golden snapshot
    snap_out_path, err = _checked_safe_path(snapshot_out, "snapshot_out")
    if err:
        return _error("step01", "init-agent", f"Invalid snapshot_out path: {err}"), 1

    assert snap_out_path is not None

    try:
        snap_out_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = capture_snapshot(
            model_file=model,
            property_file=prop,
            source_file_path=source_file_path,
        )
        snap_out_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    except Exception as exc:
        return _error("step01", "init-agent", f"snapshotter failed: {exc}"), 1

    # 5. Build and return success contract
    contract: Dict[str, Any] = {
        "status": "ok",
        "source_file_path": source_file_path,
        "rmc": {
            "jar": str(jar_path),
            "version": rmc_version,
        },
        "python": _python_env(),
        "inputs": {
            "model": str(model_path.resolve()),
            "property": str(prop_path.resolve()),
        },
        "snapshot_path": str(snap_out_path.resolve()),
    }
    return contract, 0


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="init-agent (WF-01): validate inputs, provision RMC, capture snapshot"
    )
    parser.add_argument(
        "--rule-id", required=True,
        help="Rule identifier (e.g. Rule-22)",
    )
    parser.add_argument(
        "--model", required=True,
        help="Path to .rebeca model file",
    )
    parser.add_argument(
        "--property", required=True,
        help="Path to .property file",
    )
    parser.add_argument(
        "--snapshot-out", required=True,
        help="Destination path for the golden snapshot JSON",
    )
    parser.add_argument(
        "--rmc-destination", default=None,
        help="Override RMC directory (env/marker used if omitted)",
    )

    args = parser.parse_args()

    result, exit_code = run_init(
        source_file_path=args.source_file_path,
        model=args.model,
        prop=args.property,
        snapshot_out=args.snapshot_out,
        rmc_destination=args.rmc_destination,
    )
    print(json.dumps(result, indent=2))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
