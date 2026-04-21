"""Phase E-early: FSM snapshot tests for workflow_fsm.py.

Each test constructs a synthetic artifact tree in a temp directory, invokes
the workflow_fsm.py CLI, and compares stdout JSON against a stored golden
snapshot. No real RMC invocations or step agents are used.

To regenerate golden snapshots after an intentional behavior change:
    UPDATE_FSM_SNAPSHOTS=1 pytest tests/test_workflow_fsm_snapshots.py

If a golden file is missing, the test fails with a message directing the
developer to run with UPDATE_FSM_SNAPSHOTS=1 once to create it.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / "skills" / "rebeca_tooling" / "scripts"
SNAPSHOTS = Path(__file__).parent / "fixtures" / "fsm_snapshots"

sys.path.insert(0, str(SCRIPTS))
from output_policy import step_artifact_path, report_paths  # noqa: E402

RULE_ID = "SnapTest-Rule"
_UPDATE = os.environ.get("UPDATE_FSM_SNAPSHOTS") == "1"

# Root config so budget values are real (not defaults from empty dict)
_ROOT_CONFIG = str(Path(__file__).parent.parent / "configs" / "rmc_defaults.json")

STEP_PAYLOADS: dict[str, dict] = {
    "step01_init": {
        "status": "ok",
        "source_file_path": RULE_ID,
        "snapshot_path": "/tmp/snapshot.json",
        "rmc": {"jar": "/tmp/rmc.jar", "version": "2.14"},
    },
    "step02_triage": {
        "status": "ok",
        "source_file_path": RULE_ID,
        "routing": {"path": "normal", "eligible_for_mapping": True},
        "classification": {"status": "formalized", "evidence": ["clause present"], "defects": []},
    },
    "step03_abstraction": {
        "status": "ok",
        "source_file_path": RULE_ID,
        "abstraction_summary": {"actor_map": ["Ship"], "variable_map": ["speed"], "naming_contract": {}},
    },
    "step04_mapping": {
        "status": "ok",
        "source_file_path": RULE_ID,
        "model_artifact": {"path": f"output/work/{RULE_ID}/candidates/model.rebeca"},
        "property_artifact": {"path": f"output/work/{RULE_ID}/candidates/model.property"},
    },
    "step05_candidates": {
        "status": "ok",
        "source_file_path": RULE_ID,
        "candidate_artifacts": [{
            "artifact_id": "cand-001",
            "model_path": f"output/work/{RULE_ID}/candidates/base.rebeca",
            "property_path": f"output/work/{RULE_ID}/candidates/base.property",
            "strategy": "base",
            "is_candidate": True,
            "confidence": 0.91,
            "mapping_path": "synthesis-agent",
        }],
    },
    "step06_verification_gate": {
        "status": "ok",
        "source_file_path": RULE_ID,
        "verified": True,
        "rmc_exit_code": 0,
        "rmc_output_dir": f"output/verification/{RULE_ID}/run-001",
        "vacuity_status": {"is_vacuous": False},
        "mutation_score": 90.0,
    },
    "step07_packaging_manifest": {
        "status": "ok",
        "source_file_path": RULE_ID,
        "installation_report": [{
            "artifact_id": f"{RULE_ID}_model",
            "source_path": f"output/work/{RULE_ID}/candidates/base.rebeca",
            "dest_path": f"output/{RULE_ID}/{RULE_ID}.rebeca",
            "artifact_type": "model",
            "status": "promoted",
            "reason": None,
        }],
    },
    "step08_reporting": {
        "status": "ok",
        "source_file_path": RULE_ID,
        "summary_path": f"output/reports/{RULE_ID}/summary.json",
        "summary_md_path": f"output/reports/{RULE_ID}/summary.md",
        "summary": {"total_rules": 1, "rules_passed": 1, "score_mean": 90.0},
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_artifact(step: str, data: dict, base_dir: Path) -> None:
    path = step_artifact_path(RULE_ID, step, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(path)


def _create_report_files(base_dir: Path) -> None:
    rp = report_paths(RULE_ID, base_dir)
    rp.report_dir.mkdir(parents=True, exist_ok=True)
    for fname in ("summary.json", "summary.md", "verification.json", "quality_gates.json"):
        (rp.report_dir / fname).write_text("{}", encoding="utf-8")


def _run_fsm(base_dir: Path, extra: list[str] | None = None) -> dict:
    cmd = [
        sys.executable, str(SCRIPTS / "workflow_fsm.py"),
        "--rule-id", RULE_ID,
        "--base-dir", str(base_dir),
        "--config", _ROOT_CONFIG,
    ]
    if extra:
        cmd.extend(extra)
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, f"FSM exited {result.returncode}: {result.stderr}"
    return json.loads(result.stdout)


def _normalize(action: dict, base_dir: Path) -> dict:
    """Replace base_dir occurrences with <BASE_DIR> for stable snapshots."""
    raw = json.dumps(action)
    normalized = raw.replace(str(base_dir), "<BASE_DIR>")
    return json.loads(normalized)


def _snapshot_path(name: str) -> Path:
    return SNAPSHOTS / f"{name}.json"


def _assert_snapshot(name: str, actual: dict, base_dir: Path) -> None:
    normalized = _normalize(actual, base_dir)
    golden_path = _snapshot_path(name)

    if _UPDATE or not golden_path.exists():
        SNAPSHOTS.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(json.dumps(normalized, indent=2, sort_keys=True), encoding="utf-8")
        if not _UPDATE:
            pytest.fail(
                f"Golden snapshot '{name}' did not exist — created it. "
                "Re-run without UPDATE_FSM_SNAPSHOTS to verify."
            )
        return

    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    assert normalized == golden, (
        f"Snapshot '{name}' mismatch.\n"
        f"Expected: {json.dumps(golden, indent=2)}\n"
        f"Got:      {json.dumps(normalized, indent=2)}"
    )


# ---------------------------------------------------------------------------
# Tests: happy-path progression snapshots
# ---------------------------------------------------------------------------

class TestHappyPathSnapshots:
    def test_snap_no_artifacts_run_step01(self, tmp_path: Path) -> None:
        action = _run_fsm(tmp_path)
        _assert_snapshot("run_step01_init", action, tmp_path)

    def test_snap_step01_present_run_step02(self, tmp_path: Path) -> None:
        _write_artifact("step01_init", STEP_PAYLOADS["step01_init"], tmp_path)
        action = _run_fsm(tmp_path)
        _assert_snapshot("run_step02_triage", action, tmp_path)

    def test_snap_steps_1_2_run_step03(self, tmp_path: Path) -> None:
        for s in ("step01_init", "step02_triage"):
            _write_artifact(s, STEP_PAYLOADS[s], tmp_path)
        action = _run_fsm(tmp_path)
        _assert_snapshot("run_step03_abstraction", action, tmp_path)

    def test_snap_steps_1_3_run_step04(self, tmp_path: Path) -> None:
        for s in ("step01_init", "step02_triage", "step03_abstraction"):
            _write_artifact(s, STEP_PAYLOADS[s], tmp_path)
        action = _run_fsm(tmp_path)
        _assert_snapshot("run_step04_mapping", action, tmp_path)

    def test_snap_steps_1_4_run_step05(self, tmp_path: Path) -> None:
        for s in list(STEP_PAYLOADS)[:4]:
            _write_artifact(s, STEP_PAYLOADS[s], tmp_path)
        action = _run_fsm(tmp_path)
        _assert_snapshot("run_step05_synthesis", action, tmp_path)

    def test_snap_steps_1_5_run_step06(self, tmp_path: Path) -> None:
        for s in list(STEP_PAYLOADS)[:5]:
            _write_artifact(s, STEP_PAYLOADS[s], tmp_path)
        action = _run_fsm(tmp_path)
        _assert_snapshot("run_step06_verification_gate", action, tmp_path)

    def test_snap_steps_1_6_run_step07(self, tmp_path: Path) -> None:
        for s in list(STEP_PAYLOADS)[:6]:
            _write_artifact(s, STEP_PAYLOADS[s], tmp_path)
        action = _run_fsm(tmp_path)
        _assert_snapshot("run_step07_packaging", action, tmp_path)

    def test_snap_steps_1_7_run_step08(self, tmp_path: Path) -> None:
        for s in list(STEP_PAYLOADS)[:7]:
            _write_artifact(s, STEP_PAYLOADS[s], tmp_path)
        action = _run_fsm(tmp_path)
        _assert_snapshot("run_step08_reporting", action, tmp_path)

    def test_snap_all_complete_finish(self, tmp_path: Path) -> None:
        for s, d in STEP_PAYLOADS.items():
            _write_artifact(s, d, tmp_path)
        _create_report_files(tmp_path)
        action = _run_fsm(tmp_path)
        _assert_snapshot("finish", action, tmp_path)


# ---------------------------------------------------------------------------
# Tests: refine_step (second attempt) snapshots
# ---------------------------------------------------------------------------

class TestRefineSnapshots:
    def test_snap_step01_refine(self, tmp_path: Path) -> None:
        _run_fsm(tmp_path)  # attempt 1 → run_step
        action = _run_fsm(tmp_path)  # attempt 2 → refine_step
        _assert_snapshot("refine_step01_init", action, tmp_path)

    def test_snap_step06_refine_vacuous(self, tmp_path: Path) -> None:
        for s in list(STEP_PAYLOADS)[:5]:
            _write_artifact(s, STEP_PAYLOADS[s], tmp_path)
        vacuous = copy.deepcopy(STEP_PAYLOADS["step06_verification_gate"])
        vacuous["vacuity_status"] = {"is_vacuous": True}
        _write_artifact("step06_verification_gate", vacuous, tmp_path)
        _run_fsm(tmp_path)  # attempt 1 → run_step (vacuous artifact is "present but invalid")
        action = _run_fsm(tmp_path)  # attempt 2 → refine_step
        _assert_snapshot("refine_step06_vacuous", action, tmp_path)


# ---------------------------------------------------------------------------
# Tests: budget exhaustion snapshots
# ---------------------------------------------------------------------------

class TestBudgetSnapshots:
    def test_snap_block_step01(self, tmp_path: Path) -> None:
        import json as _json
        config = _json.loads(Path(_ROOT_CONFIG).read_text())
        budget = config["max_refinement_attempts"]["default"]
        for _ in range(budget):
            _run_fsm(tmp_path)
        action = _run_fsm(tmp_path)
        _assert_snapshot("block_step01_budget_exhausted", action, tmp_path)

    def test_snap_block_step06(self, tmp_path: Path) -> None:
        import json as _json
        config = _json.loads(Path(_ROOT_CONFIG).read_text())
        budget = config["max_refinement_attempts"]["step06"]
        for s in list(STEP_PAYLOADS)[:5]:
            _write_artifact(s, STEP_PAYLOADS[s], tmp_path)
        for _ in range(budget):
            _run_fsm(tmp_path)
        action = _run_fsm(tmp_path)
        _assert_snapshot("block_step06_budget_exhausted", action, tmp_path)


# ---------------------------------------------------------------------------
# Tests: --reset snapshots
# ---------------------------------------------------------------------------

class TestResetSnapshots:
    def test_snap_reset_from_blocked_no_artifacts(self, tmp_path: Path) -> None:
        import json as _json
        config = _json.loads(Path(_ROOT_CONFIG).read_text())
        budget = config["max_refinement_attempts"]["default"]
        for _ in range(budget + 1):
            _run_fsm(tmp_path)
        action = _run_fsm(tmp_path, extra=["--reset"])
        _assert_snapshot("reset_from_blocked_no_artifacts", action, tmp_path)

    def test_snap_reset_from_clean_no_artifacts(self, tmp_path: Path) -> None:
        action = _run_fsm(tmp_path, extra=["--reset"])
        _assert_snapshot("reset_from_clean_no_artifacts", action, tmp_path)

    def test_reset_records_history_event(self, tmp_path: Path) -> None:
        _run_fsm(tmp_path)
        _run_fsm(tmp_path, extra=["--reset"])
        state_file = tmp_path / "work" / RULE_ID / "fsm_state.json"
        state = json.loads(state_file.read_text())
        events = [e["event"] for e in state["history"]]
        assert "reset" in events

    def test_reset_clears_terminal_status(self, tmp_path: Path) -> None:
        import json as _json
        config = _json.loads(Path(_ROOT_CONFIG).read_text())
        budget = config["max_refinement_attempts"]["default"]
        for _ in range(budget + 1):
            _run_fsm(tmp_path)
        _run_fsm(tmp_path, extra=["--reset"])
        state_file = tmp_path / "work" / RULE_ID / "fsm_state.json"
        state = _json.loads(state_file.read_text())
        assert state["terminal_status"] is None


# ---------------------------------------------------------------------------
# Tests: terminal state replay snapshots
# ---------------------------------------------------------------------------

class TestTerminalReplaySnapshots:
    def test_snap_finish_replays(self, tmp_path: Path) -> None:
        for s, d in STEP_PAYLOADS.items():
            _write_artifact(s, d, tmp_path)
        _create_report_files(tmp_path)
        _run_fsm(tmp_path)  # first call → sets terminal_status=finished
        action = _run_fsm(tmp_path)  # replay
        _assert_snapshot("finish_replay", action, tmp_path)

    def test_snap_block_replays(self, tmp_path: Path) -> None:
        import json as _json
        config = _json.loads(Path(_ROOT_CONFIG).read_text())
        budget = config["max_refinement_attempts"]["default"]
        for _ in range(budget + 1):
            _run_fsm(tmp_path)
        _run_fsm(tmp_path)  # first replay (sets blocked terminal)
        action = _run_fsm(tmp_path)  # second replay
        _assert_snapshot("block_replay", action, tmp_path)


# ---------------------------------------------------------------------------
# Tests: snapshot consistency — same inputs always produce same snapshot
# ---------------------------------------------------------------------------

class TestSnapshotStability:
    def test_same_artifact_tree_same_output(self, tmp_path: Path) -> None:
        """Identical artifact state + fresh FSM → identical stdout JSON."""
        import tempfile
        _write_artifact("step01_init", STEP_PAYLOADS["step01_init"], tmp_path)
        action1 = _run_fsm(tmp_path)

        with tempfile.TemporaryDirectory() as td:
            base2 = Path(td)
            _write_artifact("step01_init", STEP_PAYLOADS["step01_init"], base2)
            action2 = _run_fsm(base2)

        norm1 = _normalize(action1, tmp_path)
        norm2 = _normalize(action2, base2)
        assert norm1 == norm2, "Same artifact tree must produce identical normalized output"

    def test_snapshot_files_are_valid_json(self) -> None:
        """All stored golden snapshots must be parseable JSON."""
        if not SNAPSHOTS.exists():
            pytest.skip("No snapshot directory found — run with UPDATE_FSM_SNAPSHOTS=1 first")
        for snap_file in sorted(SNAPSHOTS.glob("*.json")):
            try:
                json.loads(snap_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                pytest.fail(f"Snapshot {snap_file.name} is invalid JSON: {exc}")

    def test_all_snapshots_have_action_field(self) -> None:
        """All stored golden snapshots must contain the top-level 'action' key."""
        if not SNAPSHOTS.exists():
            pytest.skip("No snapshot directory found — run with UPDATE_FSM_SNAPSHOTS=1 first")
        for snap_file in sorted(SNAPSHOTS.glob("*.json")):
            data = json.loads(snap_file.read_text(encoding="utf-8"))
            assert "action" in data, f"Snapshot {snap_file.name} missing 'action' field"
