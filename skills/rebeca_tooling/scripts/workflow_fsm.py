#!/usr/bin/env python3
"""workflow_fsm.py — Deterministic FSM controller for the Legata→Rebeca pipeline.

Pure decision engine: reads artifacts from disk, evaluates predicates,
writes fsm_state.json, and prints exactly one JSON action object to stdout.
Never invokes subagents, calls RMC, or writes any artifact other than fsm_state.json.

Usage:
    python workflow_fsm.py --rule-id RULE_ID [--base-dir output] [--config PATH] [--reset]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from output_policy import report_paths, step_artifact_path  # noqa: E402
from step_schemas import validate_step_output  # noqa: E402

_MUTATION_SCORE_THRESHOLD = 80.0
_DEFAULT_CONFIG = Path(__file__).parent.parent.parent.parent / "configs" / "rmc_defaults.json"


@dataclass(frozen=True)
class _PipelineStep:
    state: str
    artifact: str
    schema_key: str
    step_enum: str
    agent_enum: str
    completed_state: str


_PIPELINE: tuple[_PipelineStep, ...] = (
    _PipelineStep("start",       "step01_init",               "step01", "step01_init",              "init_agent",         "initialized"),
    _PipelineStep("initialized", "step02_triage",             "step02", "step02_triage",            "triage_agent",       "triaged"),
    _PipelineStep("triaged",     "step03_abstraction",        "step03", "step03_abstraction",       "abstraction_agent",  "abstracted"),
    _PipelineStep("abstracted",  "step04_mapping",            "step04", "step04_mapping",           "mapping_agent",      "mapped"),
    _PipelineStep("mapped",      "step05_candidates",         "step05", "step05_synthesis",         "synthesis_agent",    "synthesized"),
    _PipelineStep("synthesized", "step06_verification_gate",  "step06", "step06_verification_gate", "verification_agent", "verified"),
    _PipelineStep("verified",    "step07_packaging_manifest", "step07", "step07_packaging",         "packaging_agent",    "packaged"),
    _PipelineStep("packaged",    "step08_reporting",          "step08", "step08_reporting",         "reporting_agent",    "reported"),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_config(config_path: Path) -> dict[str, Any]:
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _get_budget(config: dict[str, Any], artifact: str) -> int:
    budgets = config.get("max_refinement_attempts", {})
    return int(budgets.get(artifact, budgets.get("default", 2)))


def _state_path(rule_id: str, base_dir: Path) -> Path:
    return base_dir / "work" / rule_id / "fsm_state.json"


def _load_state(rule_id: str, base_dir: Path) -> dict[str, Any]:
    path = _state_path(rule_id, base_dir)
    if not path.exists():
        return {
            "rule_id": rule_id,
            "current_state": "start",
            "terminal_status": None,
            "attempt_counters": {},
            "history": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _save_state(rule_id: str, base_dir: Path, state: dict[str, Any]) -> None:
    path = _state_path(rule_id, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _check_step(rule_id: str, step: _PipelineStep, base_dir: Path) -> tuple[bool, str, str]:
    """Return (is_complete, issue_class, issue_detail)."""
    path = step_artifact_path(rule_id, step.artifact, base_dir)
    if not path.exists():
        return False, "artifact_missing", "step artifact file not found"

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, "parse_error", str(exc)

    violations = validate_step_output(step.schema_key, data)
    if violations:
        return False, "schema_invalid", violations[0]

    if step.artifact == "step06_verification_gate":
        if not data.get("verified", False):
            return False, "verification_failed", "RMC returned verified=False"
        if data.get("vacuity_status", {}).get("is_vacuous", True):
            return False, "vacuous_property", "property is vacuously true"
        score = data.get("mutation_score", 0.0)
        if score < _MUTATION_SCORE_THRESHOLD:
            return False, "mutation_score_low", f"score={score} < threshold={_MUTATION_SCORE_THRESHOLD}"

    if step.artifact == "step08_reporting":
        rp = report_paths(rule_id, base_dir)
        missing = [
            f for f in ("summary.json", "summary.md", "verification.json", "quality_gates.json")
            if not (rp.report_dir / f).exists()
        ]
        if missing:
            return False, "report_incomplete", f"missing report files: {missing}"

    return True, "", ""


def _build_run_action(
    step: _PipelineStep,
    rule_id: str,
    base_dir: Path,
    attempts: int,
    issue_class: str,
    issue_detail: str,
    budget: int,
) -> dict[str, Any]:
    action_type = "run_step" if attempts == 0 else "refine_step"
    inputs: dict[str, Any] = {"rule_id": rule_id}
    if action_type == "refine_step":
        inputs.update({
            "prior_artifact_path": str(step_artifact_path(rule_id, step.artifact, base_dir)),
            "issue_class": issue_class,
            "issue_detail": issue_detail,
            "attempt_index": attempts + 1,
            "budget_remaining": budget - attempts - 1,
        })
    return {
        "status": "ok",
        "current_state": step.state,
        "next_state": step.completed_state,
        "action": {
            "type": action_type,
            "step": step.step_enum,
            "agent": step.agent_enum,
            "inputs": inputs,
        },
        "reason_code": "artifact_missing" if attempts == 0 else issue_class,
        "required_artifacts": [f"{step.artifact}.json"],
        "missing_artifacts": [f"{step.artifact}.json"],
    }


def _build_block_action(step: _PipelineStep) -> dict[str, Any]:
    return {
        "status": "blocked",
        "current_state": step.state,
        "next_state": step.state,
        "action": {"type": "block", "step": "none", "agent": "none", "inputs": {}},
        "reason_code": "budget_exhausted",
        "required_artifacts": [f"{step.artifact}.json"],
        "missing_artifacts": [f"{step.artifact}.json"],
    }


def _build_finish_action() -> dict[str, Any]:
    return {
        "status": "ok",
        "current_state": "reported",
        "next_state": "reported",
        "action": {"type": "finish", "step": "none", "agent": "none", "inputs": {}},
        "reason_code": "all_artifacts_complete",
        "required_artifacts": [],
        "missing_artifacts": [],
    }


def _replay_terminal(state: dict[str, Any]) -> dict[str, Any]:
    ts = state.get("terminal_status")
    current = state.get("current_state", "unknown")
    if ts == "finished":
        action_type, status, reason = "finish", "ok", "already_finished"
    elif ts == "blocked":
        action_type, status, reason = "block", "blocked", "budget_exhausted"
    else:
        action_type, status, reason = "error", "error", f"terminal_status_{ts}"
    return {
        "status": status,
        "current_state": current,
        "next_state": current,
        "action": {"type": action_type, "step": "none", "agent": "none", "inputs": {}},
        "reason_code": reason,
        "required_artifacts": [],
        "missing_artifacts": [],
    }


def _decide(rule_id: str, base_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    state = _load_state(rule_id, base_dir)

    if state.get("terminal_status") is not None:
        return _replay_terminal(state)

    for step in _PIPELINE:
        complete, issue_class, issue_detail = _check_step(rule_id, step, base_dir)
        if complete:
            continue

        attempts = state["attempt_counters"].get(step.artifact, 0)
        budget = _get_budget(config, step.artifact)

        if attempts >= budget:
            state["current_state"] = step.state
            state["terminal_status"] = "blocked"
            state["history"].append({
                "event": "blocked",
                "state": step.state,
                "artifact": step.artifact,
                "reason": "budget_exhausted",
                "timestamp": _now_iso(),
            })
            _save_state(rule_id, base_dir, state)
            return _build_block_action(step)

        state["attempt_counters"][step.artifact] = attempts + 1
        state["current_state"] = step.state
        state["history"].append({
            "event": "run_step" if attempts == 0 else "refine_step",
            "state": step.state,
            "artifact": step.artifact,
            "attempt": attempts + 1,
            "timestamp": _now_iso(),
        })
        _save_state(rule_id, base_dir, state)
        return _build_run_action(step, rule_id, base_dir, attempts, issue_class, issue_detail, budget)

    state["current_state"] = "reported"
    state["terminal_status"] = "finished"
    state["history"].append({"event": "finish", "timestamp": _now_iso()})
    _save_state(rule_id, base_dir, state)
    return _build_finish_action()


def _reset(rule_id: str, base_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    existing = _load_state(rule_id, base_dir)
    fresh: dict[str, Any] = {
        "rule_id": rule_id,
        "current_state": "start",
        "terminal_status": None,
        "attempt_counters": {},
        "history": existing.get("history", []) + [{
            "event": "reset",
            "from_state": existing.get("current_state", "start"),
            "timestamp": _now_iso(),
        }],
    }
    _save_state(rule_id, base_dir, fresh)
    return _decide(rule_id, base_dir, config)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministic FSM controller for the Legata→Rebeca pipeline"
    )
    parser.add_argument("--rule-id", required=True, help="Rule identifier")
    parser.add_argument("--base-dir", default="output", help="Base output directory (default: output)")
    parser.add_argument("--config", default=str(_DEFAULT_CONFIG), help="Path to rmc_defaults.json")
    parser.add_argument("--reset", action="store_true", help="Reinitialize FSM state and emit first action")
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    config = _load_config(Path(args.config))

    action = _reset(args.rule_id, base_dir, config) if args.reset else _decide(args.rule_id, base_dir, config)
    print(json.dumps(action, indent=2))


if __name__ == "__main__":
    main()
