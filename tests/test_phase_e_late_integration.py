"""Phase E-late integration + recovery + coordinator compliance tests.

Tests cover:
1. Full Step01→Step08 pipeline on synthetic artifacts:
   - All artifacts written to canonical locations and schema-valid after a run.
   - FSM advances to next state after each artifact is written.
   - Final action is `finish`.
2. Recovery: delete or corrupt an artifact mid-run; FSM identifies the gap.
3. Coordinator compliance: ProtocolSimulator implements the legata_to_rebeca.md
   executor protocol mechanically — tests prove the protocol follows FSM actions
   rather than inventing its own routing.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pytest

SCRIPTS = Path(__file__).parent.parent / "skills" / "rebeca_tooling" / "scripts"
TESTS = Path(__file__).parent

sys.path.insert(0, str(SCRIPTS))
from output_policy import step_artifact_path, report_paths  # noqa: E402
from step_schemas import validate_step_output  # noqa: E402

RULE_ID = "ELate-Rule"
_ROOT_CONFIG = str(Path(__file__).parent.parent / "configs" / "rmc_defaults.json")

# Map FSM action.step enum → artifact_writer --step argument
# (diverges for step05 and step07)
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

# Map FSM action.step enum → schema validation key
_STEP_ENUM_TO_SCHEMA: dict[str, str] = {
    "step01_init":              "step01",
    "step02_triage":            "step02",
    "step03_abstraction":       "step03",
    "step04_mapping":           "step04",
    "step05_synthesis":         "step05",
    "step06_verification_gate": "step06",
    "step07_packaging":         "step07",
    "step08_reporting":         "step08",
}

MOCK_PAYLOADS: dict[str, dict] = {
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
    "step05_synthesis": {
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
    "step07_packaging": {
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


# ---------------------------------------------------------------------------
# ProtocolSimulator — faithful implementation of the legata_to_rebeca.md
# executor protocol. Used by compliance tests to prove the protocol follows
# FSM actions rather than inventing routing.
# ---------------------------------------------------------------------------

@dataclass
class Invocation:
    agent: str
    step_enum: str
    inputs: dict[str, Any]


@dataclass
class ProtocolSimulator:
    """Implements the three-part executor protocol from legata_to_rebeca.md."""

    rule_id: str
    base_dir: Path
    agent_responses: dict[str, dict]   # step_enum → mock agent JSON output
    fsm_callable: Callable[..., dict] | None = None
    invocations: list[Invocation] = field(default_factory=list)

    def run(self, max_iterations: int = 20) -> dict:
        """Execute protocol; return the terminal action."""
        state_path = self.base_dir / "work" / self.rule_id / "fsm_state.json"

        # Part 1 — Conditional Reset
        needs_reset = not state_path.exists()
        if not needs_reset:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            needs_reset = state.get("terminal_status") is not None
        action = self._call_fsm(reset=needs_reset)

        # Part 2 — Execution Loop
        iterations = 0
        while action["action"]["type"] in ("run_step", "refine_step"):
            if iterations >= max_iterations:
                raise RuntimeError(f"Executor loop exceeded {max_iterations} iterations")
            iterations += 1

            step_enum = action["action"]["step"]
            agent = action["action"]["agent"]
            inputs = action["action"]["inputs"]

            # Record invocation for compliance assertions
            self.invocations.append(Invocation(agent=agent, step_enum=step_enum, inputs=inputs))

            # Invoke mapped agent (mock)
            payload = self.agent_responses.get(step_enum)
            if payload is None:
                raise ValueError(f"No mock response registered for step: {step_enum!r}")

            # Persist canonical artifact
            artifact_step = _STEP_ENUM_TO_ARTIFACT[step_enum]
            self._write_artifact(artifact_step, payload)

            # step08 also needs report files to let FSM advance past it
            if step_enum == "step08_reporting":
                self._create_report_files()

            action = self._call_fsm(reset=False)

        # Part 3 — Terminal Handling (caller inspects returned action)
        return action

    def _call_fsm(self, reset: bool = False) -> dict:
        if self.fsm_callable is not None:
            return self.fsm_callable(reset=reset)
        cmd = [
            sys.executable, str(SCRIPTS / "workflow_fsm.py"),
            "--rule-id", self.rule_id,
            "--base-dir", str(self.base_dir),
            "--config", _ROOT_CONFIG,
        ]
        if reset:
            cmd.append("--reset")
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0, f"FSM exited {result.returncode}: {result.stderr}"
        return json.loads(result.stdout)

    def _write_artifact(self, artifact_step: str, data: dict) -> None:
        result = subprocess.run(
            [
                sys.executable, str(SCRIPTS / "artifact_writer.py"),
                "--rule-id", self.rule_id,
                "--step", artifact_step,
                "--data", json.dumps(data),
                "--base-dir", str(self.base_dir),
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"artifact_writer failed: {result.stderr}"

    def _create_report_files(self) -> None:
        rp = report_paths(self.rule_id, self.base_dir)
        rp.report_dir.mkdir(parents=True, exist_ok=True)
        for fname in ("summary.json", "summary.md", "verification.json", "quality_gates.json"):
            (rp.report_dir / fname).write_text("{}", encoding="utf-8")


def _make_simulator(base_dir: Path, payloads: dict | None = None) -> ProtocolSimulator:
    return ProtocolSimulator(
        rule_id=RULE_ID,
        base_dir=base_dir,
        agent_responses=payloads or copy.deepcopy(MOCK_PAYLOADS),
    )


# ---------------------------------------------------------------------------
# Tests: full pipeline integration
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    def test_full_pipeline_terminates_with_finish(self, tmp_path: Path) -> None:
        sim = _make_simulator(tmp_path)
        final = sim.run()
        assert final["action"]["type"] == "finish"

    def test_all_artifacts_exist_at_canonical_paths_after_run(self, tmp_path: Path) -> None:
        _make_simulator(tmp_path).run()
        for step_enum, artifact_step in _STEP_ENUM_TO_ARTIFACT.items():
            path = step_artifact_path(RULE_ID, artifact_step, tmp_path)
            assert path.exists(), f"Missing artifact: {path}"

    def test_all_artifacts_are_schema_valid_after_run(self, tmp_path: Path) -> None:
        _make_simulator(tmp_path).run()
        for step_enum, artifact_step in _STEP_ENUM_TO_ARTIFACT.items():
            schema_key = _STEP_ENUM_TO_SCHEMA[step_enum]
            path = step_artifact_path(RULE_ID, artifact_step, tmp_path)
            data = json.loads(path.read_text(encoding="utf-8"))
            errors = validate_step_output(schema_key, data)
            assert errors == [], f"{artifact_step}: schema violations after run: {errors}"

    def test_agents_invoked_in_correct_order(self, tmp_path: Path) -> None:
        sim = _make_simulator(tmp_path)
        sim.run()
        expected_agents = [
            "init_agent", "triage_agent", "abstraction_agent", "mapping_agent",
            "synthesis_agent", "verification_agent", "packaging_agent", "reporting_agent",
        ]
        actual_agents = [inv.agent for inv in sim.invocations]
        assert actual_agents == expected_agents

    def test_fsm_state_is_finished_after_full_run(self, tmp_path: Path) -> None:
        _make_simulator(tmp_path).run()
        state_path = tmp_path / "work" / RULE_ID / "fsm_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["terminal_status"] == "finished"
        assert state["current_state"] == "reported"

    def test_all_eight_steps_are_executed(self, tmp_path: Path) -> None:
        sim = _make_simulator(tmp_path)
        sim.run()
        assert len(sim.invocations) == 8


# ---------------------------------------------------------------------------
# Tests: FSM step-by-step advancement
# ---------------------------------------------------------------------------

class TestFsmAdvancement:
    def test_fsm_state_advances_after_each_artifact(self, tmp_path: Path) -> None:
        """After writing each artifact, FSM should advance past it without re-requesting it."""
        from workflow_fsm import _decide, _load_state
        sys.path.insert(0, str(SCRIPTS))
        config = json.loads(Path(_ROOT_CONFIG).read_text())

        for i, (step_enum, artifact_step) in enumerate(_STEP_ENUM_TO_ARTIFACT.items()):
            payload = MOCK_PAYLOADS[step_enum]
            path = step_artifact_path(RULE_ID, artifact_step, tmp_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")

            if step_enum == "step08_reporting":
                rp = report_paths(RULE_ID, tmp_path)
                rp.report_dir.mkdir(parents=True, exist_ok=True)
                for fname in ("summary.json", "summary.md", "verification.json", "quality_gates.json"):
                    (rp.report_dir / fname).write_text("{}")

            action = _decide(RULE_ID, tmp_path, config)
            if i < 7:
                # Should be asking for the NEXT step, not this one
                assert action["action"]["step"] != step_enum, (
                    f"After writing {artifact_step}, FSM still requests {step_enum}"
                )
            else:
                # All 8 done → finish
                assert action["action"]["type"] == "finish"

    def test_fsm_does_not_re_request_completed_steps(self, tmp_path: Path) -> None:
        """Once step01 artifact is written, FSM must never emit run_step step01_init again."""
        sim = _make_simulator(tmp_path)
        sim.run()
        step01_requests = [inv for inv in sim.invocations if inv.step_enum == "step01_init"]
        assert len(step01_requests) == 1


# ---------------------------------------------------------------------------
# Tests: recovery behavior
# ---------------------------------------------------------------------------

class TestPipelineRecovery:
    def test_resume_from_partial_run_without_reset(self, tmp_path: Path) -> None:
        """Write steps 1–4, then run simulator; it should only call steps 5–8."""
        partial_steps = ("step01_init", "step02_triage", "step03_abstraction", "step04_mapping")
        for step_enum in partial_steps:
            artifact_step = _STEP_ENUM_TO_ARTIFACT[step_enum]
            path = step_artifact_path(RULE_ID, artifact_step, tmp_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(MOCK_PAYLOADS[step_enum]))

        sim = _make_simulator(tmp_path)
        final = sim.run()
        assert final["action"]["type"] == "finish"

        invoked_steps = [inv.step_enum for inv in sim.invocations]
        for already_done in partial_steps:
            assert already_done not in invoked_steps, (
                f"Step {already_done} was re-run despite artifact already existing"
            )
        assert invoked_steps == [
            "step05_synthesis", "step06_verification_gate",
            "step07_packaging", "step08_reporting",
        ]

    def test_fsm_identifies_single_deleted_artifact(self, tmp_path: Path) -> None:
        """After a full run, delete step04 artifact; FSM must request step04 again."""
        from workflow_fsm import _decide, _reset
        config = json.loads(Path(_ROOT_CONFIG).read_text())

        sim = _make_simulator(tmp_path)
        sim.run()

        # Delete step04 artifact and reset FSM so it re-evaluates
        step04_path = step_artifact_path(RULE_ID, "step04_mapping", tmp_path)
        step04_path.unlink()
        _reset(RULE_ID, tmp_path, config)

        action = _decide(RULE_ID, tmp_path, config)
        assert action["action"]["step"] == "step04_mapping", (
            f"Expected step04_mapping after deletion, got: {action['action']['step']}"
        )
        assert action["current_state"] == "abstracted"

    def test_fsm_advances_past_restored_artifact(self, tmp_path: Path) -> None:
        """After restoring a deleted artifact, FSM should skip past it to the next missing step."""
        from workflow_fsm import _decide, _reset
        config = json.loads(Path(_ROOT_CONFIG).read_text())

        sim = _make_simulator(tmp_path)
        sim.run()

        step04_path = step_artifact_path(RULE_ID, "step04_mapping", tmp_path)
        step04_path.unlink()
        _reset(RULE_ID, tmp_path, config)

        # Restore the artifact
        step04_path.write_text(json.dumps(MOCK_PAYLOADS["step04_mapping"]))

        # FSM should now skip step04 and ask for the next missing step
        # (step05 was present, step06 was present, etc. — so should be finish)
        action = _decide(RULE_ID, tmp_path, config)
        assert action["action"]["type"] == "finish", (
            f"Expected finish after restoring all artifacts, got: {action['action']}"
        )

    def test_corrupted_artifact_triggers_run_step_not_advance(self, tmp_path: Path) -> None:
        """A JSON-corrupted artifact must not allow FSM to advance past that step."""
        from workflow_fsm import _decide, _reset
        config = json.loads(Path(_ROOT_CONFIG).read_text())

        # Write all artifacts, finish the pipeline
        sim = _make_simulator(tmp_path)
        sim.run()

        # Corrupt step03 then reset — _reset internally calls _decide once (attempt 1)
        step03_path = step_artifact_path(RULE_ID, "step03_abstraction", tmp_path)
        step03_path.write_text("{ not valid json !!!")
        action = _reset(RULE_ID, tmp_path, config)

        # _reset's internal _decide is attempt 1 → run_step (no issue_class in inputs)
        assert action["action"]["step"] == "step03_abstraction"
        assert action["action"]["type"] == "run_step"
        assert "issue_class" not in action["action"]["inputs"]

    def test_schema_invalid_artifact_triggers_run_step(self, tmp_path: Path) -> None:
        """An artifact that fails schema validation must block FSM advancement."""
        from workflow_fsm import _decide, _reset
        config = json.loads(Path(_ROOT_CONFIG).read_text())

        sim = _make_simulator(tmp_path)
        sim.run()

        # Replace step05 with a skeleton (missing required candidate_artifacts)
        step05_path = step_artifact_path(RULE_ID, "step05_candidates", tmp_path)
        step05_path.write_text(json.dumps({"status": "ok"}))
        _reset(RULE_ID, tmp_path, config)

        action = _decide(RULE_ID, tmp_path, config)
        assert action["action"]["step"] == "step05_synthesis"

    def test_partial_run_state_without_fsm_state_file_uses_disk(self, tmp_path: Path) -> None:
        """No fsm_state.json present → simulator must call --reset; FSM derives state from disk."""
        # Write steps 1-2 directly (no FSM state file)
        for step_enum in ("step01_init", "step02_triage"):
            artifact_step = _STEP_ENUM_TO_ARTIFACT[step_enum]
            path = step_artifact_path(RULE_ID, artifact_step, tmp_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(MOCK_PAYLOADS[step_enum]))

        state_path = tmp_path / "work" / RULE_ID / "fsm_state.json"
        assert not state_path.exists()

        sim = _make_simulator(tmp_path)
        final = sim.run()
        assert final["action"]["type"] == "finish"

        invoked = [inv.step_enum for inv in sim.invocations]
        assert "step01_init" not in invoked
        assert "step02_triage" not in invoked
        assert "step03_abstraction" in invoked


# ---------------------------------------------------------------------------
# Tests: coordinator compliance
# ---------------------------------------------------------------------------

class TestCoordinatorCompliance:
    """Prove that ProtocolSimulator (the coordinator) follows FSM actions exactly.

    Uses a mock FSM callable to inject specific action sequences and verifies
    the simulator invokes the right agents with the right inputs — catching
    coordinators that invent routing instead of following FSM output.
    """

    def test_simulator_invokes_agent_matching_fsm_action(self, tmp_path: Path) -> None:
        """If FSM emits action.agent=mapping_agent, exactly mapping_agent must be called."""
        action_sequence = [
            {
                "status": "ok",
                "current_state": "abstracted",
                "next_state": "mapped",
                "action": {"type": "run_step", "step": "step04_mapping",
                           "agent": "mapping_agent", "inputs": {"rule_id": RULE_ID}},
                "reason_code": "artifact_missing",
                "required_artifacts": ["step04_mapping.json"],
                "missing_artifacts": ["step04_mapping.json"],
            },
            {
                "status": "ok",
                "current_state": "reported",
                "next_state": "reported",
                "action": {"type": "finish", "step": "none", "agent": "none", "inputs": {}},
                "reason_code": "all_artifacts_complete",
                "required_artifacts": [],
                "missing_artifacts": [],
            },
        ]
        call_count = [0]

        def mock_fsm(reset: bool = False) -> dict:
            idx = min(call_count[0], len(action_sequence) - 1)
            call_count[0] += 1
            return action_sequence[idx]

        sim = ProtocolSimulator(
            rule_id=RULE_ID,
            base_dir=tmp_path,
            agent_responses={"step04_mapping": MOCK_PAYLOADS["step04_mapping"]},
            fsm_callable=mock_fsm,
        )
        final = sim.run()

        assert final["action"]["type"] == "finish"
        assert len(sim.invocations) == 1
        assert sim.invocations[0].agent == "mapping_agent"
        assert sim.invocations[0].step_enum == "step04_mapping"

    def test_simulator_passes_inputs_verbatim(self, tmp_path: Path) -> None:
        """action.inputs must reach the agent call unchanged — no key stripping or adding."""
        custom_inputs = {"rule_id": RULE_ID, "custom_key": "sentinel_value_xyz", "attempt_index": 7}
        action_sequence = [
            {
                "status": "ok",
                "current_state": "start",
                "next_state": "initialized",
                "action": {"type": "run_step", "step": "step01_init",
                           "agent": "init_agent", "inputs": custom_inputs},
                "reason_code": "artifact_missing",
                "required_artifacts": ["step01_init.json"],
                "missing_artifacts": ["step01_init.json"],
            },
            {
                "status": "ok",
                "current_state": "reported",
                "next_state": "reported",
                "action": {"type": "finish", "step": "none", "agent": "none", "inputs": {}},
                "reason_code": "all_artifacts_complete",
                "required_artifacts": [],
                "missing_artifacts": [],
            },
        ]
        call_count = [0]

        def mock_fsm(reset: bool = False) -> dict:
            idx = min(call_count[0], len(action_sequence) - 1)
            call_count[0] += 1
            return action_sequence[idx]

        sim = ProtocolSimulator(
            rule_id=RULE_ID,
            base_dir=tmp_path,
            agent_responses={"step01_init": MOCK_PAYLOADS["step01_init"]},
            fsm_callable=mock_fsm,
        )
        sim.run()

        assert sim.invocations[0].inputs == custom_inputs

    def test_simulator_stops_on_finish_without_further_agent_calls(self, tmp_path: Path) -> None:
        call_count = [0]

        def mock_fsm(reset: bool = False) -> dict:
            call_count[0] += 1
            return {
                "status": "ok",
                "current_state": "reported",
                "next_state": "reported",
                "action": {"type": "finish", "step": "none", "agent": "none", "inputs": {}},
                "reason_code": "all_artifacts_complete",
                "required_artifacts": [],
                "missing_artifacts": [],
            }

        sim = ProtocolSimulator(
            rule_id=RULE_ID,
            base_dir=tmp_path,
            agent_responses={},
            fsm_callable=mock_fsm,
        )
        final = sim.run()
        assert final["action"]["type"] == "finish"
        assert sim.invocations == []
        assert call_count[0] == 1  # exactly one FSM call (the reset/initial call)

    def test_simulator_stops_on_block(self, tmp_path: Path) -> None:
        def mock_fsm(reset: bool = False) -> dict:
            return {
                "status": "blocked",
                "current_state": "start",
                "next_state": "start",
                "action": {"type": "block", "step": "none", "agent": "none", "inputs": {}},
                "reason_code": "budget_exhausted",
                "required_artifacts": ["step01_init.json"],
                "missing_artifacts": ["step01_init.json"],
            }

        sim = ProtocolSimulator(
            rule_id=RULE_ID,
            base_dir=tmp_path,
            agent_responses={},
            fsm_callable=mock_fsm,
        )
        final = sim.run()
        assert final["action"]["type"] == "block"
        assert sim.invocations == []

    def test_wrong_agent_is_never_called(self, tmp_path: Path) -> None:
        """FSM says triage_agent; compliance requires ONLY triage_agent is called, not others."""
        action_sequence = [
            {
                "status": "ok",
                "current_state": "initialized",
                "next_state": "triaged",
                "action": {"type": "run_step", "step": "step02_triage",
                           "agent": "triage_agent", "inputs": {"rule_id": RULE_ID}},
                "reason_code": "artifact_missing",
                "required_artifacts": ["step02_triage.json"],
                "missing_artifacts": ["step02_triage.json"],
            },
            {
                "status": "ok",
                "current_state": "reported",
                "next_state": "reported",
                "action": {"type": "finish", "step": "none", "agent": "none", "inputs": {}},
                "reason_code": "all_artifacts_complete",
                "required_artifacts": [],
                "missing_artifacts": [],
            },
        ]
        call_count = [0]

        def mock_fsm(reset: bool = False) -> dict:
            idx = min(call_count[0], len(action_sequence) - 1)
            call_count[0] += 1
            return action_sequence[idx]

        sim = ProtocolSimulator(
            rule_id=RULE_ID,
            base_dir=tmp_path,
            agent_responses={"step02_triage": MOCK_PAYLOADS["step02_triage"]},
            fsm_callable=mock_fsm,
        )
        sim.run()

        agents_called = {inv.agent for inv in sim.invocations}
        assert agents_called == {"triage_agent"}
        assert "mapping_agent" not in agents_called
        assert "init_agent" not in agents_called

    def test_refine_step_inputs_contain_feedback_fields(self, tmp_path: Path) -> None:
        """For refine_step actions, action.inputs must include FSM feedback fields verbatim."""
        refine_inputs = {
            "rule_id": RULE_ID,
            "prior_artifact_path": f"<BASE_DIR>/work/{RULE_ID}/step04_mapping.json",
            "issue_class": "schema_invalid",
            "issue_detail": "missing required key: model_artifact",
            "attempt_index": 2,
            "budget_remaining": 1,
        }
        action_sequence = [
            {
                "status": "ok",
                "current_state": "abstracted",
                "next_state": "mapped",
                "action": {"type": "refine_step", "step": "step04_mapping",
                           "agent": "mapping_agent", "inputs": refine_inputs},
                "reason_code": "schema_invalid",
                "required_artifacts": ["step04_mapping.json"],
                "missing_artifacts": ["step04_mapping.json"],
            },
            {
                "status": "ok",
                "current_state": "reported",
                "next_state": "reported",
                "action": {"type": "finish", "step": "none", "agent": "none", "inputs": {}},
                "reason_code": "all_artifacts_complete",
                "required_artifacts": [],
                "missing_artifacts": [],
            },
        ]
        call_count = [0]

        def mock_fsm(reset: bool = False) -> dict:
            idx = min(call_count[0], len(action_sequence) - 1)
            call_count[0] += 1
            return action_sequence[idx]

        sim = ProtocolSimulator(
            rule_id=RULE_ID,
            base_dir=tmp_path,
            agent_responses={"step04_mapping": MOCK_PAYLOADS["step04_mapping"]},
            fsm_callable=mock_fsm,
        )
        sim.run()

        assert sim.invocations[0].inputs == refine_inputs
        assert sim.invocations[0].inputs["issue_class"] == "schema_invalid"
        assert sim.invocations[0].inputs["attempt_index"] == 2
