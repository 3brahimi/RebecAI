#!/usr/bin/env python3
"""Verify installed artifacts."""

import argparse
import sys
from pathlib import Path

from utils import safe_path


def verify_installation(target_root: str) -> int:
    """
    Verify installed artifacts exist.
    
    Returns:
        0: All artifacts present
        1: Missing artifacts
    """
    target_path = safe_path(target_root)
    missing = 0
    
    # Check agent
    agent_path = target_path / "agents" / "legata-formalization.agent.md"
    if not agent_path.exists():
        print("✗ Agent not found")
        missing += 1
    else:
        print("✓ Agent found")
    
    # Check workflow skill
    workflow_path = target_path / "skills" / "legata-formalization-workflow"
    if not workflow_path.is_dir():
        print("✗ Workflow skill not found")
        missing += 1
    else:
        print("✓ Workflow skill found")
    
    # Check modeling guidelines skill
    modeling_path = target_path / "skills" / "rebeca-modeling-guidelines"
    if not modeling_path.is_dir():
        print("✗ Modeling guidelines skill not found")
        missing += 1
    else:
        print("✓ Modeling guidelines skill found")
    
    if missing == 0:
        print("✓ All artifacts verified")
        return 0
    else:
        print(f"✗ {missing} artifact(s) missing")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Verify installed artifacts")
    parser.add_argument("target_root", nargs="?", default=".", help="Target installation directory")
    
    args = parser.parse_args()
    sys.exit(verify_installation(args.target_root))


if __name__ == "__main__":
    main()
