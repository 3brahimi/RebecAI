"""Phase F rollout tests: feature flag, full-auto pipeline runner, shadow parity gate.

Tests cover:
1. FSM_CONTROLLER_ENABLED=0 (or unset) → exit 2 + deprecation message.
2. FSM_CONTROLLER_ENABLED=1 + mock agents → pipeline runs to finish.
3. run_pipeline.py exit codes: 0=finish, 3=block.
4. shadow_compare.py parity gate: identical runs → passed; divergent → failed.
5. shadow_compare.py divergence detection: missing artifact, schema-invalid artifact,
   missing report file.
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
MOCK_AGENTS_DIR = Path(__file__).parent / "fixtures" / "mock_agents"

sys.path.insert(0, str(SCRIPTS))
from output_policy import step_artifact_path, report_paths  # noqa: E402
from step_schemas import validate_step_output  # noqa: E402

RULE_ID = "PhaseF-Rule"
_ROOT_CONFIG = str(Path(__file__).parent.parent / "configs" / "rmc_defaults.json")


def _run_pipeline(
    rule_id: str,
    base_dir: Path,
    mock_agents_dir: Path | None = None,
    flag: str = "1",
    extra: list[str] | None = None,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["FSM_CONTROLLER_ENABLED"] = flag
    cmd = [
        sys.executable, str(SCRIPTS / "run_pipeline.py"),
        "--rule-id", rule_id,
        "--base-dir", str(base_dir),
        "--config", _ROOT_CONFIG,
    ]
    if mock_agents_dir:
        cmd += ["--mock-agents-dir", str(mock_agents_dir)]
    if extra:
        cmd.extend(extra)
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def _run_shadow_compare(
    rule_id: str,
    baseline_dir: Path,
    fsm_dir: Path,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable, str(SCRIPTS / "shadow_compare.py"),
            "--rule-id", rule_id,
            "--baseline-dir", str(baseline_dir),
            "--fsm-dir", str(fsm_dir),
        ],
        capture_output=True, text=True,
    )


def _write_artifact(rule_id: str, step: str, data: dict, base_dir: Path) -> None:
    path = step_artifact_path(rule_id, step, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _load_mock(step_enum: str) -> dict:
    return json.loads((MOCK_AGENTS_DIR / f"{step_enum}.json").read_text())


_STEP_ENUM_TO_ARTIFACT = {
    "step01_init": "step01_init",
    "step02_triage": "step02_triage",
    "step03_abstraction": "step03_abstraction",
    "step04_mapping": "step04_mapping",
    "step05_synthesis": "step05_candidates",
    "step06_verification_gate": "step06_verification_gate",
    "step07_packaging": "step07_packaging_manifest",
    "step08_reporting": "step08_reporting",
}

_STEP_ENUM_TO_SCHEMA = {
    "step01_init": "step01",
    "step02_triage": "step02",
    "step03_abstraction": "step03",
    "step04_mapping": "step04",
    "step05_synthesis": "step05",
    "step06_verification_gate": "step06",
    "step07_packaging": "step07",
    "step08_reporting": "step08",
}


def _write_full_run(rule_id: str, base_dir: Path) -> None:
    for step_enum, artifact_step in _STEP_ENUM_TO_ARTIFACT.items():
        _write_artifact(rule_id, artifact_step, _load_mock(step_enum), base_dir)
    rp = report_paths(rule_id, base_dir)
    rp.report_dir.mkdir(parents=True, exist_ok=True)
    for fname in ("summary.json", "summary.md", "verification.json", "quality_gates.json"):
        (rp.report_dir / fname).write_text("{}", encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests: feature flag
# ---------------------------------------------------------------------------

class TestFeatureFlag:
    def test_flag_unset_exits_2(self, tmp_path: Path) -> None:
        result = _run_pipeline(RULE_ID, tmp_path, flag="0")
        assert result.returncode == 2

    def test_flag_zero_prints_deprecation(self, tmp_path: Path) -> None:
        result = _run_pipeline(RULE_ID, tmp_path, flag="0")
        assert "FSM_CONTROLLER_ENABLED" in result.stderr
        assert "deprecated" in result.stderr.lower() or "removed" in result.stderr.lower()

    def test_flag_one_does_not_exit_2(self, tmp_path: Path) -> None:
        result = _run_pipeline(RULE_ID, tmp_path, mock_agents_dir=MOCK_AGENTS_DIR, flag="1")
        assert result.returncode != 2

    def test_env_var_not_set_behaves_as_zero(self, tmp_path: Path) -> None:
        env = os.environ.copy()
        env.pop("FSM_CONTROLLER_ENABLED", None)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "run_pipeline.py"),
             "--rule-id", RULE_ID, "--base-dir", str(tmp_path)],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 2


# ---------------------------------------------------------------------------
# Tests: run_pipeline.py full-auto mode
# ---------------------------------------------------------------------------

class TestRunPipelineFullAuto:
    def test_full_run_exits_0(self, tmp_path: Path) -> None:
        result = _run_pipeline(RULE_ID, tmp_path, mock_agents_dir=MOCK_AGENTS_DIR)
        assert result.returncode == 0, result.stderr

    def test_full_run_terminal_action_is_finish(self, tmp_path: Path) -> None:
        result = _run_pipeline(RULE_ID, tmp_path, mock_agents_dir=MOCK_AGENTS_DIR)
        lines = [l for l in result.stdout.strip().splitlines() if l.startswith("{")]
        terminal = json.loads(lines[-1])
        assert terminal["action"]["type"] == "finish"

    def test_full_run_all_artifacts_present(self, tmp_path: Path) -> None:
        _run_pipeline(RULE_ID, tmp_path, mock_agents_dir=MOCK_AGENTS_DIR)
        for artifact_step in _STEP_ENUM_TO_ARTIFACT.values():
            path = step_artifact_path(RULE_ID, artifact_step, tmp_path)
            assert path.exists(), f"Missing after full run: {artifact_step}"

    def test_full_run_all_artifacts_schema_valid(self, tmp_path: Path) -> None:
        _run_pipeline(RULE_ID, tmp_path, mock_agents_dir=MOCK_AGENTS_DIR)
        for step_enum, artifact_step in _STEP_ENUM_TO_ARTIFACT.items():
            schema_key = _STEP_ENUM_TO_SCHEMA[step_enum]
            data = json.loads(step_artifact_path(RULE_ID, artifact_step, tmp_path).read_text())
            errors = validate_step_output(schema_key, data)
            assert errors == [], f"{artifact_step}: {errors}"

    def test_block_exit_code_is_3(self, tmp_path: Path) -> None:
        """When FSM blocks (budget exhausted), run_pipeline exits 3."""
        config_data = json.loads(Path(_ROOT_CONFIG).read_text())
        budget = config_data["max_refinement_attempts"]["default"]

        # Exhaust budget for step01 by calling run_pipeline without mock responses
        # (no artifact written → FSM keeps requesting → block)
        env = os.environ.copy()
        env["FSM_CONTROLLER_ENABLED"] = "1"
        for _ in range(budget):
            subprocess.run(
                [sys.executable, str(SCRIPTS / "run_pipeline.py"),
                 "--rule-id", RULE_ID, "--base-dir", str(tmp_path),
                 "--config", _ROOT_CONFIG],
                capture_output=True, text=True, env=env,
            )

        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "run_pipeline.py"),
             "--rule-id", RULE_ID, "--base-dir", str(tmp_path),
             "--config", _ROOT_CONFIG],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 3

    def test_missing_mock_fixture_raises_error(self, tmp_path: Path) -> None:
        empty_fixtures = tmp_path / "empty_fixtures"
        empty_fixtures.mkdir()
        result = _run_pipeline(RULE_ID, tmp_path, mock_agents_dir=empty_fixtures)
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# Tests: shadow_compare.py parity gate
# ---------------------------------------------------------------------------

class TestShadowCompare:
    def test_identical_runs_pass_parity_gate(self, tmp_path: Path) -> None:
        baseline = tmp_path / "baseline"
        fsm_dir = tmp_path / "fsm"
        _write_full_run(RULE_ID, baseline)
        _write_full_run(RULE_ID, fsm_dir)
        result = _run_shadow_compare(RULE_ID, baseline, fsm_dir)
        report = json.loads(result.stdout)
        assert result.returncode == 0
        assert report["parity_gate_passed"] is True
        assert report["divergences"] == []

    def test_missing_artifact_in_fsm_fails_gate(self, tmp_path: Path) -> None:
        baseline = tmp_path / "baseline"
        fsm_dir = tmp_path / "fsm"
        _write_full_run(RULE_ID, baseline)
        _write_full_run(RULE_ID, fsm_dir)
        # Remove step04 from FSM run
        step_artifact_path(RULE_ID, "step04_mapping", fsm_dir).unlink()
        result = _run_shadow_compare(RULE_ID, baseline, fsm_dir)
        report = json.loads(result.stdout)
        assert result.returncode == 1
        assert report["parity_gate_passed"] is False
        types = {d["type"] for d in report["divergences"]}
        assert "presence_mismatch" in types

    def test_missing_artifact_in_baseline_fails_gate(self, tmp_path: Path) -> None:
        baseline = tmp_path / "baseline"
        fsm_dir = tmp_path / "fsm"
        _write_full_run(RULE_ID, baseline)
        _write_full_run(RULE_ID, fsm_dir)
        step_artifact_path(RULE_ID, "step02_triage", baseline).unlink()
        result = _run_shadow_compare(RULE_ID, baseline, fsm_dir)
        report = json.loads(result.stdout)
        assert report["parity_gate_passed"] is False

    def test_schema_invalid_artifact_fails_gate(self, tmp_path: Path) -> None:
        baseline = tmp_path / "baseline"
        fsm_dir = tmp_path / "fsm"
        _write_full_run(RULE_ID, baseline)
        _write_full_run(RULE_ID, fsm_dir)
        # Make step06 schema-invalid in fsm run (missing required 'verified' field)
        step06_path = step_artifact_path(RULE_ID, "step06_verification_gate", fsm_dir)
        step06_path.write_text(json.dumps({"status": "ok"}))
        result = _run_shadow_compare(RULE_ID, baseline, fsm_dir)
        report = json.loads(result.stdout)
        assert report["parity_gate_passed"] is False
        assert "step06_verification_gate" in report["fsm_invalid_artifacts"]

    def test_missing_report_file_fails_gate(self, tmp_path: Path) -> None:
        baseline = tmp_path / "baseline"
        fsm_dir = tmp_path / "fsm"
        _write_full_run(RULE_ID, baseline)
        _write_full_run(RULE_ID, fsm_dir)
        (report_paths(RULE_ID, fsm_dir).report_dir / "quality_gates.json").unlink()
        result = _run_shadow_compare(RULE_ID, baseline, fsm_dir)
        report = json.loads(result.stdout)
        assert report["parity_gate_passed"] is False
        types = {d["type"] for d in report["divergences"]}
        assert "report_file_mismatch" in types

    def test_both_runs_empty_fails_gate(self, tmp_path: Path) -> None:
        """Two empty dirs (no artifacts) — neither run is valid, gate must fail."""
        baseline = tmp_path / "baseline"
        fsm_dir = tmp_path / "fsm"
        result = _run_shadow_compare(RULE_ID, baseline, fsm_dir)
        report = json.loads(result.stdout)
        assert report["parity_gate_passed"] is False

    def test_json_output_flag_writes_file(self, tmp_path: Path) -> None:
        baseline = tmp_path / "baseline"
        fsm_dir = tmp_path / "fsm"
        _write_full_run(RULE_ID, baseline)
        _write_full_run(RULE_ID, fsm_dir)
        out_path = tmp_path / "results" / "parity.json"
        subprocess.run(
            [sys.executable, str(SCRIPTS / "shadow_compare.py"),
             "--rule-id", RULE_ID,
             "--baseline-dir", str(baseline),
             "--fsm-dir", str(fsm_dir),
             "--json-output", str(out_path)],
            capture_output=True, text=True,
        )
        assert out_path.exists()
        data = json.loads(out_path.read_text())
        assert "parity_gate_passed" in data

    def test_divergence_report_identifies_specific_artifact(self, tmp_path: Path) -> None:
        baseline = tmp_path / "baseline"
        fsm_dir = tmp_path / "fsm"
        _write_full_run(RULE_ID, baseline)
        _write_full_run(RULE_ID, fsm_dir)
        step_artifact_path(RULE_ID, "step05_candidates", fsm_dir).unlink()
        result = _run_shadow_compare(RULE_ID, baseline, fsm_dir)
        report = json.loads(result.stdout)
        diverged_artifacts = [d.get("artifact") for d in report["divergences"]]
        assert "step05_candidates" in diverged_artifacts
