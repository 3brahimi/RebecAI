#!/usr/bin/env python3
"""Verify installed artifacts."""

import argparse
import sys
from pathlib import Path
from typing import Iterable

from utils import safe_path


REQUIRED_SKILLS = (
    "legata_to_rebeca",
    "rebeca_tooling",
    "rebeca_handbook",
    "rebeca_mutation",
    "rebeca_hallucination",
)


def _exists_any(paths: Iterable[Path]) -> bool:
    return any(p.exists() for p in paths)


def verify_installation(target_root: str) -> int:
    """
    Verify installed artifacts exist.

    Returns:
        0: All artifacts present
        1: Missing artifacts
    """
    target_path = safe_path(target_root)
    missing = 0

    # Check coordinator agent (support current + legacy naming variants)
    coordinator_candidates = (
        target_path / "agents" / "legata_to_rebeca.md",
        target_path / "agents" / "legata-to-rebeca.md",
        target_path / "agents" / "legata-formalization.agent.md",
        target_path / "agents" / "legata_to_rebeca.agent.md",
        target_path / "agents" / "legata-to-rebeca.agent.md",
    )
    if not _exists_any(coordinator_candidates):
        print("✗ Coordinator agent not found")
        missing += 1
    else:
        print("✓ Coordinator agent found")

    # Check required skills for current coordinator contract.
    missing_skills = [name for name in REQUIRED_SKILLS if not (target_path / "skills" / name).is_dir()]
    if missing_skills:
        for name in missing_skills:
            print(f"✗ Skill not found: {name}")
        missing += len(missing_skills)
    else:
        print("✓ Required skills found")

    # FSM config check — warn mode (not a hard failure yet)
    config_path = target_path / "configs" / "rmc_defaults.json"
    if not config_path.exists():
        print("⚠ FSM config not found: configs/rmc_defaults.json (FSM budget enforcement will use hardcoded defaults)")
    else:
        print("✓ FSM config found: configs/rmc_defaults.json")

    # FSM controller check — warn mode
    fsm_script = target_path / "skills" / "rebeca_tooling" / "scripts" / "workflow_fsm.py"
    if not fsm_script.exists():
        print("⚠ FSM controller not found: skills/rebeca_tooling/scripts/workflow_fsm.py")
    else:
        print("✓ FSM controller found")

    if missing == 0:
        print("✓ All artifacts verified")
        return 0
    else:
        print(f"✗ {missing} artifact(s) missing")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Verify installed artifacts")
    parser.add_argument("target_root", nargs="?", default=".", help="Target installation directory")
    # --rmc-jar accepted for backward-compatibility with earlier skill docs that
    # suggested passing the jar path here; the value is recorded but not used
    # by the artifact-presence checks (jar validation is in pre_run_rmc_check.py).
    parser.add_argument("--rmc-jar", default=None,
                        help="(Ignored) Path to rmc.jar — accepted for CLI compatibility")

    args = parser.parse_args()
    sys.exit(verify_installation(args.target_root))


if __name__ == "__main__":
    main()
