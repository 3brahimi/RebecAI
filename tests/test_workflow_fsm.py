"""Phase C tests: workflow_fsm.py — deterministic FSM controller.

Tests cover:
1. Fresh start (no state, no artifacts) → run_step step01_init
2. Incremental artifact presence → correct step advancement
3. Budget exhaustion → block terminal action
4. --reset clears state and re-evaluates from disk
5. refine_step emitted on second attempt with correct inputs
6. Terminal replay (finish/block) emits correct action without mutating state
7. step06 special predicates: verified=False, vacuous, mutation_score_low
8. step08 special predicate: artifact present but report files missing
9. fsm_state.json written atomically with correct structure
10. All FSM outputs are fsm_action schema-valid
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / "skills" / "rebeca_tooling" / "scripts"
TESTS = Path(__file__).parent

sys.path.insert(0, str(SCRIPTS))
from step_schemas import validate_step_output, STEP_OUTPUT_SCHEMAS  # noqa: E402
from output_policy import step_artifact_path, report_paths  # noqa: E402
from workflow_fsm import _decide, _reset, _load_state, _check_step, _PIPELINE, _PipelineStep  # noqa: E402

RULE_ID = "FsmTest-Rule"

_CONFIG = {
    "max_refinement_attempts": {
        "step04_mapping": 3,
        "step05_candidates": 3,
        "step06_verification_gate": 2,
        "default": 2,
    }
}

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
        "abstraction_summary": {
            "actor_map": ["Ship"],
            "variable_map": ["speed"],
            "naming_contract": {},
        },
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
        "report_path": f"output/reports/{RULE_ID}/summary.json",
        "report_md_path": f"output/reports/{RULE_ID}/summary.md",
        "summary": {"total_rules": 1, "rules_passed": 1, "score_mean": 90.0},
    },
}


def _write_artifact(rule_id: str, step: str, data: dict, base_dir: Path) -> None:
    path = step_artifact_path(rule_id, step, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(path)


def _write_all_artifacts(base_dir: Path) -> None:
    for step, data in STEP_PAYLOADS.items():
        _write_artifact(RULE_ID, step, data, base_dir)


def _create_report_files(base_dir: Path) -> None:
    rp = report_paths(RULE_ID, base_dir)
    rp.report_dir.mkdir(parents=True, exist_ok=True)
    for fname in ("summary.json", "summary.md", "verification.json", "quality_gates.json"):
        (rp.report_dir / fname).write_text("{}", encoding="utf-8")


def _assert_fsm_action_valid(action: dict) -> None:
    errors = validate_step_output("fsm_action", action)
    assert errors == [], f"fsm_action schema violations: {errors}"


# ---------------------------------------------------------------------------
# Tests: basic state transitions
# ---------------------------------------------------------------------------

class TestFreshStart:
    def test_no_artifacts_emits_run_step01(self, tmp_path: Path) -> None:
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        assert action["action"]["type"] == "run_step"
        assert action["action"]["step"] == "step01_init"
        assert action["action"]["agent"] == "init_agent"

    def test_current_state_is_start(self, tmp_path: Path) -> None:
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        assert action["current_state"] == "start"
        assert action["next_state"] == "initialized"

    def test_missing_artifact_in_required_artifacts(self, tmp_path: Path) -> None:
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        assert "step01_init.json" in action["missing_artifacts"]
        assert "step01_init.json" in action["required_artifacts"]

    def test_reason_code_artifact_missing(self, tmp_path: Path) -> None:
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        assert action["reason_code"] == "artifact_missing"

    def test_status_ok(self, tmp_path: Path) -> None:
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        assert action["status"] == "ok"

    def test_output_is_fsm_action_schema_valid(self, tmp_path: Path) -> None:
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        _assert_fsm_action_valid(action)


class TestIncrementalAdvancement:
    def test_step01_present_emits_step02(self, tmp_path: Path) -> None:
        _write_artifact(RULE_ID, "step01_init", STEP_PAYLOADS["step01_init"], tmp_path)
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        assert action["action"]["step"] == "step02_triage"
        assert action["current_state"] == "initialized"

    def test_steps_1_2_present_emits_step03(self, tmp_path: Path) -> None:
        for s in ("step01_init", "step02_triage"):
            _write_artifact(RULE_ID, s, STEP_PAYLOADS[s], tmp_path)
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        assert action["action"]["step"] == "step03_abstraction"
        assert action["current_state"] == "triaged"

    def test_steps_1_through_7_emits_step08(self, tmp_path: Path) -> None:
        for s in list(STEP_PAYLOADS)[:-1]:
            _write_artifact(RULE_ID, s, STEP_PAYLOADS[s], tmp_path)
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        assert action["action"]["step"] == "step08_reporting"
        assert action["current_state"] == "packaged"

    def test_all_artifacts_and_reports_emits_finish(self, tmp_path: Path) -> None:
        _write_all_artifacts(tmp_path)
        _create_report_files(tmp_path)
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        assert action["action"]["type"] == "finish"
        assert action["current_state"] == "reported"

    def test_all_artifacts_and_reports_schema_valid(self, tmp_path: Path) -> None:
        _write_all_artifacts(tmp_path)
        _create_report_files(tmp_path)
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        _assert_fsm_action_valid(action)


# ---------------------------------------------------------------------------
# Tests: attempt counting and refine_step
# ---------------------------------------------------------------------------

class TestAttemptCounters:
    def test_second_call_emits_refine_step(self, tmp_path: Path) -> None:
        _decide(RULE_ID, tmp_path, _CONFIG)  # first call → run_step, increments to 1
        action = _decide(RULE_ID, tmp_path, _CONFIG)  # second call
        assert action["action"]["type"] == "refine_step"

    def test_refine_step_has_required_inputs(self, tmp_path: Path) -> None:
        _decide(RULE_ID, tmp_path, _CONFIG)
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        inputs = action["action"]["inputs"]
        for key in ("prior_artifact_path", "issue_class", "issue_detail", "attempt_index", "budget_remaining"):
            assert key in inputs, f"Missing refine_step input: {key}"

    def test_refine_step_attempt_index(self, tmp_path: Path) -> None:
        _decide(RULE_ID, tmp_path, _CONFIG)
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        assert action["action"]["inputs"]["attempt_index"] == 2

    def test_refine_step_budget_remaining(self, tmp_path: Path) -> None:
        _decide(RULE_ID, tmp_path, _CONFIG)
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        default_budget = _CONFIG["max_refinement_attempts"]["default"]
        assert action["action"]["inputs"]["budget_remaining"] == default_budget - 2

    def test_attempt_counter_persisted_in_state(self, tmp_path: Path) -> None:
        _decide(RULE_ID, tmp_path, _CONFIG)
        state = _load_state(RULE_ID, tmp_path)
        assert state["attempt_counters"].get("step01_init", 0) == 1

    def test_refine_step_schema_valid(self, tmp_path: Path) -> None:
        _decide(RULE_ID, tmp_path, _CONFIG)
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        _assert_fsm_action_valid(action)


# ---------------------------------------------------------------------------
# Tests: budget exhaustion → block
# ---------------------------------------------------------------------------

class TestBudgetExhaustion:
    def test_block_after_budget_exhausted(self, tmp_path: Path) -> None:
        budget = _CONFIG["max_refinement_attempts"]["default"]
        for _ in range(budget):
            _decide(RULE_ID, tmp_path, _CONFIG)
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        assert action["action"]["type"] == "block"
        assert action["status"] == "blocked"
        assert action["reason_code"] == "budget_exhausted"

    def test_block_sets_terminal_status(self, tmp_path: Path) -> None:
        budget = _CONFIG["max_refinement_attempts"]["default"]
        for _ in range(budget + 1):
            _decide(RULE_ID, tmp_path, _CONFIG)
        state = _load_state(RULE_ID, tmp_path)
        assert state["terminal_status"] == "blocked"

    def test_blocked_replays_on_subsequent_call(self, tmp_path: Path) -> None:
        budget = _CONFIG["max_refinement_attempts"]["default"]
        for _ in range(budget + 1):
            _decide(RULE_ID, tmp_path, _CONFIG)
        action1 = _decide(RULE_ID, tmp_path, _CONFIG)
        action2 = _decide(RULE_ID, tmp_path, _CONFIG)
        assert action1["action"]["type"] == "block"
        assert action2["action"]["type"] == "block"

    def test_step06_has_its_own_budget(self, tmp_path: Path) -> None:
        for s in list(STEP_PAYLOADS)[:5]:
            _write_artifact(RULE_ID, s, STEP_PAYLOADS[s], tmp_path)
        # step06 budget is 2 in our test config
        budget = _CONFIG["max_refinement_attempts"]["step06_verification_gate"]
        for _ in range(budget):
            _decide(RULE_ID, tmp_path, _CONFIG)
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        assert action["action"]["type"] == "block"

    def test_block_schema_valid(self, tmp_path: Path) -> None:
        budget = _CONFIG["max_refinement_attempts"]["default"]
        for _ in range(budget + 1):
            _decide(RULE_ID, tmp_path, _CONFIG)
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        _assert_fsm_action_valid(action)


# ---------------------------------------------------------------------------
# Tests: reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_clears_attempt_counters(self, tmp_path: Path) -> None:
        _decide(RULE_ID, tmp_path, _CONFIG)
        _decide(RULE_ID, tmp_path, _CONFIG)
        # Before reset: step01_init attempt counter is 2
        state_before = _load_state(RULE_ID, tmp_path)
        assert state_before["attempt_counters"]["step01_init"] == 2

        _reset(RULE_ID, tmp_path, _CONFIG)  # clears counters, then calls _decide (adds attempt 1)
        state = _load_state(RULE_ID, tmp_path)
        # Counter reset to 1 (fresh first attempt), not still at 2
        assert state["attempt_counters"].get("step01_init", 0) == 1

    def test_reset_clears_terminal_status(self, tmp_path: Path) -> None:
        budget = _CONFIG["max_refinement_attempts"]["default"]
        for _ in range(budget + 1):
            _decide(RULE_ID, tmp_path, _CONFIG)
        _reset(RULE_ID, tmp_path, _CONFIG)
        state = _load_state(RULE_ID, tmp_path)
        assert state["terminal_status"] is None

    def test_reset_records_history_event(self, tmp_path: Path) -> None:
        _decide(RULE_ID, tmp_path, _CONFIG)
        _reset(RULE_ID, tmp_path, _CONFIG)
        state = _load_state(RULE_ID, tmp_path)
        events = [e["event"] for e in state["history"]]
        assert "reset" in events

    def test_reset_preserves_prior_history(self, tmp_path: Path) -> None:
        _decide(RULE_ID, tmp_path, _CONFIG)
        _reset(RULE_ID, tmp_path, _CONFIG)
        state = _load_state(RULE_ID, tmp_path)
        assert len(state["history"]) >= 2  # original run_step + reset

    def test_reset_with_artifacts_present_advances(self, tmp_path: Path) -> None:
        _write_all_artifacts(tmp_path)
        _create_report_files(tmp_path)
        _decide(RULE_ID, tmp_path, _CONFIG)  # sets terminal_status=finished
        action = _reset(RULE_ID, tmp_path, _CONFIG)
        assert action["action"]["type"] == "finish"

    def test_reset_emits_run_step01_when_no_artifacts(self, tmp_path: Path) -> None:
        action = _reset(RULE_ID, tmp_path, _CONFIG)
        assert action["action"]["step"] == "step01_init"

    def test_reset_schema_valid(self, tmp_path: Path) -> None:
        action = _reset(RULE_ID, tmp_path, _CONFIG)
        _assert_fsm_action_valid(action)


# ---------------------------------------------------------------------------
# Tests: terminal replay
# ---------------------------------------------------------------------------

class TestTerminalReplay:
    def test_finish_replays_without_state_change(self, tmp_path: Path) -> None:
        _write_all_artifacts(tmp_path)
        _create_report_files(tmp_path)
        _decide(RULE_ID, tmp_path, _CONFIG)  # sets terminal_status=finished
        state_before = _load_state(RULE_ID, tmp_path)
        _decide(RULE_ID, tmp_path, _CONFIG)  # replay
        state_after = _load_state(RULE_ID, tmp_path)
        assert state_before["history"] == state_after["history"]

    def test_finish_replay_action_type(self, tmp_path: Path) -> None:
        _write_all_artifacts(tmp_path)
        _create_report_files(tmp_path)
        _decide(RULE_ID, tmp_path, _CONFIG)
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        assert action["action"]["type"] == "finish"

    def test_finish_replay_schema_valid(self, tmp_path: Path) -> None:
        _write_all_artifacts(tmp_path)
        _create_report_files(tmp_path)
        _decide(RULE_ID, tmp_path, _CONFIG)
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        _assert_fsm_action_valid(action)


# ---------------------------------------------------------------------------
# Tests: step06 special predicates
# ---------------------------------------------------------------------------

class TestStep06Predicates:
    def _setup(self, tmp_path: Path) -> None:
        for s in list(STEP_PAYLOADS)[:5]:
            _write_artifact(RULE_ID, s, STEP_PAYLOADS[s], tmp_path)

    def test_verified_false_fails_check(self, tmp_path: Path) -> None:
        self._setup(tmp_path)
        failing = copy.deepcopy(STEP_PAYLOADS["step06_verification_gate"])
        failing["verified"] = False
        _write_artifact(RULE_ID, "step06_verification_gate", failing, tmp_path)
        step = next(s for s in _PIPELINE if s.artifact == "step06_verification_gate")
        ok, issue_class, _ = _check_step(RULE_ID, step, tmp_path)
        assert not ok
        assert issue_class == "verification_failed"

    def test_vacuous_fails_check(self, tmp_path: Path) -> None:
        self._setup(tmp_path)
        vacuous = copy.deepcopy(STEP_PAYLOADS["step06_verification_gate"])
        vacuous["vacuity_status"] = {"is_vacuous": True}
        _write_artifact(RULE_ID, "step06_verification_gate", vacuous, tmp_path)
        step = next(s for s in _PIPELINE if s.artifact == "step06_verification_gate")
        ok, issue_class, _ = _check_step(RULE_ID, step, tmp_path)
        assert not ok
        assert issue_class == "vacuous_property"

    def test_low_mutation_score_fails_check(self, tmp_path: Path) -> None:
        self._setup(tmp_path)
        low = copy.deepcopy(STEP_PAYLOADS["step06_verification_gate"])
        low["mutation_score"] = 40.0
        _write_artifact(RULE_ID, "step06_verification_gate", low, tmp_path)
        step = next(s for s in _PIPELINE if s.artifact == "step06_verification_gate")
        ok, issue_class, _ = _check_step(RULE_ID, step, tmp_path)
        assert not ok
        assert issue_class == "mutation_score_low"

    def test_step06_passes_with_good_artifact(self, tmp_path: Path) -> None:
        self._setup(tmp_path)
        _write_artifact(RULE_ID, "step06_verification_gate", STEP_PAYLOADS["step06_verification_gate"], tmp_path)
        step = next(s for s in _PIPELINE if s.artifact == "step06_verification_gate")
        ok, _, _ = _check_step(RULE_ID, step, tmp_path)
        assert ok

    def test_fsm_emits_refine_for_vacuous(self, tmp_path: Path) -> None:
        self._setup(tmp_path)
        vacuous = copy.deepcopy(STEP_PAYLOADS["step06_verification_gate"])
        vacuous["vacuity_status"] = {"is_vacuous": True}
        _write_artifact(RULE_ID, "step06_verification_gate", vacuous, tmp_path)
        _decide(RULE_ID, tmp_path, _CONFIG)  # run_step attempt 1
        action = _decide(RULE_ID, tmp_path, _CONFIG)  # refine
        assert action["action"]["type"] == "refine_step"
        assert action["action"]["inputs"]["issue_class"] == "vacuous_property"


# ---------------------------------------------------------------------------
# Tests: step08 report files predicate
# ---------------------------------------------------------------------------

class TestStep08Predicate:
    def test_step08_artifact_present_but_no_reports_fails(self, tmp_path: Path) -> None:
        _write_all_artifacts(tmp_path)
        # Deliberately no report files
        step = next(s for s in _PIPELINE if s.artifact == "step08_reporting")
        ok, issue_class, _ = _check_step(RULE_ID, step, tmp_path)
        assert not ok
        assert issue_class == "report_incomplete"

    def test_step08_passes_with_all_report_files(self, tmp_path: Path) -> None:
        _write_all_artifacts(tmp_path)
        _create_report_files(tmp_path)
        step = next(s for s in _PIPELINE if s.artifact == "step08_reporting")
        ok, _, _ = _check_step(RULE_ID, step, tmp_path)
        assert ok

    def test_fsm_emits_run_step08_when_report_missing(self, tmp_path: Path) -> None:
        _write_all_artifacts(tmp_path)
        action = _decide(RULE_ID, tmp_path, _CONFIG)
        assert action["action"]["step"] == "step08_reporting"


# ---------------------------------------------------------------------------
# Tests: fsm_state.json structure and atomicity
# ---------------------------------------------------------------------------

class TestStateFile:
    def test_state_file_created_on_first_decide(self, tmp_path: Path) -> None:
        _decide(RULE_ID, tmp_path, _CONFIG)
        state_file = tmp_path / "work" / RULE_ID / "fsm_state.json"
        assert state_file.exists()

    def test_state_file_is_valid_json(self, tmp_path: Path) -> None:
        _decide(RULE_ID, tmp_path, _CONFIG)
        state_file = tmp_path / "work" / RULE_ID / "fsm_state.json"
        data = json.loads(state_file.read_text())
        assert "current_state" in data
        assert "attempt_counters" in data
        assert "history" in data

    def test_no_tmp_file_left_behind(self, tmp_path: Path) -> None:
        _decide(RULE_ID, tmp_path, _CONFIG)
        work_dir = tmp_path / "work" / RULE_ID
        tmp_files = list(work_dir.glob("*.tmp"))
        assert tmp_files == [], f"Leftover .tmp files: {tmp_files}"

    def test_history_has_run_step_event(self, tmp_path: Path) -> None:
        _decide(RULE_ID, tmp_path, _CONFIG)
        state = _load_state(RULE_ID, tmp_path)
        assert any(e["event"] == "run_step" for e in state["history"])

    def test_deterministic_output_same_inputs(self, tmp_path: Path) -> None:
        """Same artifact tree + fresh state → identical action output."""
        _write_artifact(RULE_ID, "step01_init", STEP_PAYLOADS["step01_init"], tmp_path)
        action1 = _decide(RULE_ID, tmp_path, _CONFIG)

        import tempfile
        with tempfile.TemporaryDirectory() as td:
            base2 = Path(td)
            _write_artifact(RULE_ID, "step01_init", STEP_PAYLOADS["step01_init"], base2)
            action2 = _decide(RULE_ID, base2, _CONFIG)

        # Strip timestamps from history before comparing
        for a in (action1, action2):
            a.pop("timestamp", None)
        assert action1["action"] == action2["action"]
        assert action1["current_state"] == action2["current_state"]
        assert action1["next_state"] == action2["next_state"]


# ---------------------------------------------------------------------------
# Tests: CLI integration (subprocess)
# ---------------------------------------------------------------------------

class TestCLI:
    def _run(self, rule_id: str, base_dir: Path, extra: list[str] | None = None) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPTS / "workflow_fsm.py"), "--rule-id", rule_id, "--base-dir", str(base_dir)]
        if extra:
            cmd.extend(extra)
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_cli_exits_zero_no_artifacts(self, tmp_path: Path) -> None:
        result = self._run(RULE_ID, tmp_path)
        assert result.returncode == 0, result.stderr

    def test_cli_prints_json_to_stdout(self, tmp_path: Path) -> None:
        result = self._run(RULE_ID, tmp_path)
        data = json.loads(result.stdout)
        assert "action" in data

    def test_cli_no_extra_output(self, tmp_path: Path) -> None:
        result = self._run(RULE_ID, tmp_path)
        # Only JSON should be on stdout — parseable as a single JSON object
        json.loads(result.stdout)

    def test_cli_reset_flag(self, tmp_path: Path) -> None:
        self._run(RULE_ID, tmp_path)
        result = self._run(RULE_ID, tmp_path, ["--reset"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "action" in data

    def test_cli_missing_rule_id_exits_nonzero(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "workflow_fsm.py"), "--base-dir", str(tmp_path)],
            capture_output=True, text=True,
        )
        assert result.returncode != 0

    def test_cli_full_pipeline_emits_finish(self, tmp_path: Path) -> None:
        _write_all_artifacts(tmp_path)
        _create_report_files(tmp_path)
        result = self._run(RULE_ID, tmp_path)
        data = json.loads(result.stdout)
        assert data["action"]["type"] == "finish"


# ---------------------------------------------------------------------------
# Tests: default config path and budget consumption
# ---------------------------------------------------------------------------

class TestDefaultConfigPath:
    def test_default_config_file_exists(self) -> None:
        from workflow_fsm import _DEFAULT_CONFIG
        assert _DEFAULT_CONFIG.exists(), f"Default config not found: {_DEFAULT_CONFIG}"

    def test_default_config_has_max_refinement_attempts(self) -> None:
        from workflow_fsm import _DEFAULT_CONFIG
        import json
        data = json.loads(_DEFAULT_CONFIG.read_text(encoding="utf-8"))
        assert "max_refinement_attempts" in data

    def test_step06_budget_consumed_from_root_config(self, tmp_path: Path) -> None:
        """FSM must consume step06_verification_gate budget from root configs/rmc_defaults.json."""
        from workflow_fsm import _DEFAULT_CONFIG, _load_config, _get_budget
        config = _load_config(_DEFAULT_CONFIG)
        budget = _get_budget(config, "step06_verification_gate")
        # root config has step06: 2; default: 2 — either way must be > 0
        assert budget > 0, "Budget must come from real config, not fallback empty dict"

        # Simulate reaching the step06 decision point
        for s in list(STEP_PAYLOADS)[:5]:
            _write_artifact(RULE_ID, s, STEP_PAYLOADS[s], tmp_path)

        # Exhaust exactly that many attempts using the real config
        for _ in range(budget):
            _decide(RULE_ID, tmp_path, config)
        action = _decide(RULE_ID, tmp_path, config)
        assert action["action"]["type"] == "block"
        assert action["reason_code"] == "budget_exhausted"

    def test_cli_uses_default_config_without_flag(self, tmp_path: Path) -> None:
        """CLI without --config must resolve to existing root config (not silently missing)."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "workflow_fsm.py"), "--rule-id", RULE_ID, "--base-dir", str(tmp_path)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        # If config loaded successfully, action is well-formed
        assert "action" in data
        assert data["action"]["type"] in ("run_step", "refine_step", "finish", "block", "skip", "error")
