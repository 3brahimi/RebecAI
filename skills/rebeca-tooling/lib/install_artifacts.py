#!/usr/bin/env python3
"""Install generated artifacts to target location."""

import argparse
import shutil
import sys
from pathlib import Path
from typing import List, Tuple


def install_artifacts(target_root: str, mode: str = "all") -> int:
    """
    Install agent and skill artifacts.
    
    Args:
        target_root: Target installation directory
        mode: Installation mode (agent|skill|all)
    
    Returns:
        0: Success
        1: Validation error or installation failure
    """
    if mode not in ("agent", "skill", "all"):
        print(f"Error: --mode must be agent, skill, or all", file=sys.stderr)
        return 1
    
    # Determine project root (claude-rebeca/)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent if script_dir.name == "lib" else script_dir.parent
    
    target_path = Path(target_root)
    install_count = 0
    
    # Source paths
    agent_src = project_root / "agents" / "legata-formalization.agent.md"
    workflow_skill_src = project_root / "skills" / "legata-formalization-workflow"
    modeling_skill_src = project_root / "skills" / "rebeca-modeling-guidelines"
    
    # Install agent
    if mode in ("all", "agent"):
        if agent_src.exists():
            agent_dest = target_path / "agents"
            agent_dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(agent_src, agent_dest / agent_src.name)
            print(f"✓ Installed agent → {agent_dest}/")
            install_count += 1
        else:
            print(f"⚠ Agent source not found: {agent_src}")
    
    # Install skills
    if mode in ("all", "skill"):
        skills_dest = target_path / "skills"
        skills_dest.mkdir(parents=True, exist_ok=True)
        
        if workflow_skill_src.exists():
            dest = skills_dest / workflow_skill_src.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(workflow_skill_src, dest)
            print(f"✓ Installed workflow skill → {skills_dest}/")
            install_count += 1
        else:
            print(f"⚠ Workflow skill source not found: {workflow_skill_src}")
        
        if modeling_skill_src.exists():
            dest = skills_dest / modeling_skill_src.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(modeling_skill_src, dest)
            print(f"✓ Installed modeling guidelines skill → {skills_dest}/")
            install_count += 1
        else:
            print(f"⚠ Modeling skill source not found: {modeling_skill_src}")
    
    print(f"Installation complete: {install_count} artifacts installed to {target_root}")
    
    # Verify installed artifacts
    print("\nPost-install verification:")
    verify_pass = True
    
    if mode in ("all", "agent"):
        agent_installed = (target_path / "agents" / "legata-formalization.agent.md").exists()
        if agent_installed:
            print("  ✓ Agent present")
        else:
            print("  ✗ Agent missing after install")
            verify_pass = False
    
    if mode in ("all", "skill"):
        workflow_installed = (target_path / "skills" / "legata-formalization-workflow" / "SKILL.md").exists()
        modeling_installed = (target_path / "skills" / "rebeca-modeling-guidelines" / "SKILL.md").exists()
        
        if workflow_installed:
            print("  ✓ Workflow skill present")
        else:
            print("  ✗ Workflow skill missing after install")
            verify_pass = False
        
        if modeling_installed:
            print("  ✓ Modeling guidelines skill present")
        else:
            print("  ✗ Modeling guidelines skill missing after install")
            verify_pass = False
    
    if verify_pass:
        print("All artifacts verified.")
        return 0
    else:
        print("Verification failed: some artifacts missing after install.")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Install agent and skill artifacts")
    parser.add_argument("--target-root", required=True, help="Target installation directory")
    parser.add_argument("--mode", default="all", choices=["agent", "skill", "all"], help="Installation mode")
    
    args = parser.parse_args()
    sys.exit(install_artifacts(args.target_root, args.mode))


if __name__ == "__main__":
    main()
