#!/usr/bin/env python3
"""run_pipeline.py — Feature-flagged executor loop for the Legata→Rebeca pipeline.

Feature flag (env var, default "0"):
    FSM_CONTROLLER_ENABLED=0  Deprecated legacy path. Emits a migration warning
                               and exits 2. The embedded-guard coordinator was
                               removed in Phase D; set the flag to 1 to proceed.
    FSM_CONTROLLER_ENABLED=1  FSM executor protocol (Phase D). Drives the
                               pipeline via workflow_fsm.py until a terminal
                               action is received.

Usage:
    # Single-action mode: print next FSM action and exit (coordinator reads it)
    FSM_CONTROLLER_ENABLED=1 python run_pipeline.py --rule-id RULE_ID

    # Full-auto mode: run entire loop using mock agent responses from fixtures dir
    FSM_CONTROLLER_ENABLED=1 python run_pipeline.py --rule-id RULE_ID \\
        --mock-agents-dir tests/fixtures/mock_agents/

    # Dry-run: print each FSM action without calling artifact_writer
    FSM_CONTROLLER_ENABLED=1 python run_pipeline.py --rule-id RULE_ID \\
        --mock-agents-dir ... --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from output_policy import report_paths, step_artifact_path  # noqa: E402

_SCRIPTS = Path(__file__).parent
_DEFAULT_CONFIG = Path(__file__).parent.parent.parent.parent / "configs" / "rmc_defaults.json"

# Map FSM action.step enum → artifact_writer --step argument
_STEP_ENUM_TO_ARTIFACT: dict[str, str] = {
    "step01_init":              "step01_init",
    "step02_triage":            "step02_triage",
    "step03_abstraction":       "step03_abstraction",
    "step04_mapping":           "step04_mapping",
    "step05_synthesis":         "step05_candidates",
    "step06_verification_gate": "step06_verification_gate",
    "step07_packaging":         "step07_packaging_manifest",
    "step08_reporting":         "step08_reporting",
}

_TERMINAL_ACTIONS = frozenset({"finish", "block", "skip", "error"})

_DEPRECATION_MSG = """\
ERROR: FSM_CONTROLLER_ENABLED=0 (or unset).

The embedded-guard coordinator was removed in Phase D of the FSM migration.
There is no legacy orchestration path to run.

To use the pipeline, set:
    FSM_CONTROLLER_ENABLED=1

and invoke this script as the FSM executor loop, or use workflow_fsm.py directly
for single-step decisions.
"""


def _call_fsm(rule_id: str, base_dir: Path, config: Path, reset: bool = False) -> dict:
    cmd = [
        sys.executable, str(_SCRIPTS / "workflow_fsm.py"),
        "--rule-id", rule_id,
        "--base-dir", str(base_dir),
        "--config", str(config),
    ]
    if reset:
        cmd.append("--reset")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"workflow_fsm.py exited {result.returncode}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def _write_artifact(rule_id: str, step_enum: str, data: dict, base_dir: Path) -> None:
    artifact_step = _STEP_ENUM_TO_ARTIFACT[step_enum]
    result = subprocess.run(
        [
            sys.executable, str(_SCRIPTS / "artifact_writer.py"),
            "--rule-id", rule_id,
            "--step", artifact_step,
            "--data", json.dumps(data),
            "--base-dir", str(base_dir),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"artifact_writer.py failed for {step_enum}: {result.stderr.strip()}")


def _write_report_stubs(rule_id: str, base_dir: Path) -> None:
    rp = report_paths(rule_id, base_dir)
    rp.report_dir.mkdir(parents=True, exist_ok=True)
    for fname in ("summary.json", "summary.md", "verification.json", "quality_gates.json"):
        target = rp.report_dir / fname
        if not target.exists():
            target.write_text("{}", encoding="utf-8")


def _needs_reset(rule_id: str, base_dir: Path) -> bool:
    state_path = base_dir / "work" / rule_id / "fsm_state.json"
    if not state_path.exists():
        return True
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        return state.get("terminal_status") is not None
    except (json.JSONDecodeError, KeyError):
        return True


def run_fsm_loop(
    rule_id: str,
    base_dir: Path,
    config: Path,
    mock_agents_dir: Path | None,
    dry_run: bool,
    max_iterations: int = 20,
) -> dict:
    """Execute the Phase D executor protocol. Returns the terminal action."""
    reset = _needs_reset(rule_id, base_dir)
    action = _call_fsm(rule_id, base_dir, config, reset=reset)

    iterations = 0
    while action["action"]["type"] not in _TERMINAL_ACTIONS:
        if iterations >= max_iterations:
            raise RuntimeError(f"Executor loop exceeded {max_iterations} iterations — possible cycle")
        iterations += 1

        step_enum = action["action"]["step"]
        agent = action["action"]["agent"]
        inputs = action["action"]["inputs"]

        print(
            json.dumps({"iteration": iterations, "action_type": action["action"]["type"],
                        "step": step_enum, "agent": agent}),
            flush=True,
        )

        if dry_run:
            print(f"[dry-run] would invoke {agent} for {step_enum} with inputs: {inputs}")
            break

        if mock_agents_dir is None:
            # Single-action mode: print action for the coordinator and stop
            print(json.dumps(action))
            return action

        # Load mock agent response
        fixture_path = mock_agents_dir / f"{step_enum}.json"
        if not fixture_path.exists():
            raise FileNotFoundError(
                f"Mock agent fixture missing for step {step_enum!r}: {fixture_path}"
            )
        agent_output = json.loads(fixture_path.read_text(encoding="utf-8"))
        _write_artifact(rule_id, step_enum, agent_output, base_dir)

        # step08 requires report files to satisfy the FSM's completion check
        if step_enum == "step08_reporting":
            _write_report_stubs(rule_id, base_dir)

        action = _call_fsm(rule_id, base_dir, config, reset=False)

    return action


def main() -> None:
    flag = os.environ.get("FSM_CONTROLLER_ENABLED", "0")
    if flag != "1":
        print(_DEPRECATION_MSG, file=sys.stderr)
        sys.exit(2)

    parser = argparse.ArgumentParser(
        description="FSM-driven pipeline executor (Phase D protocol)"
    )
    parser.add_argument("--rule-id", required=True, help="Rule identifier")
    parser.add_argument("--base-dir", default="output", help="Base output directory")
    parser.add_argument("--config", default=str(_DEFAULT_CONFIG), help="Path to rmc_defaults.json")
    parser.add_argument(
        "--mock-agents-dir",
        help="Directory of <step_enum>.json mock agent responses for full-auto mode",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print each FSM action without invoking artifact_writer",
    )
    parser.add_argument("--max-iterations", type=int, default=20)
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    config = Path(args.config)
    mock_dir = Path(args.mock_agents_dir) if args.mock_agents_dir else None

    terminal = run_fsm_loop(
        rule_id=args.rule_id,
        base_dir=base_dir,
        config=config,
        mock_agents_dir=mock_dir,
        dry_run=args.dry_run,
        max_iterations=args.max_iterations,
    )

    print(json.dumps(terminal))

    if terminal["action"]["type"] == "finish":
        sys.exit(0)
    elif terminal["action"]["type"] == "block":
        sys.exit(3)
    elif terminal["action"]["type"] == "skip":
        sys.exit(4)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
