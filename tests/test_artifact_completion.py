"""Phase B integration tests: verify every step produces a canonical durable artifact.

These tests prove that:
1. artifact_writer.py writes atomically (tmp→rename) and produces schema-valid JSON.
2. Each step's VALID_FIXTURE passes its schema and can be written/read back via artifact_writer.
3. A complete simulated pipeline (all 8 artifacts + required report files) passes Gate 0.
4. Re-running artifact_writer.py with identical data produces identical artifacts (idempotent).
5. A partial run (missing any one artifact) fails Gate 0.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCRIPTS = Path(__file__).parent.parent / "skills" / "rebeca_tooling" / "scripts"
TESTS = Path(__file__).parent

sys.path.insert(0, str(SCRIPTS))
from step_schemas import validate_step_output, STEP_OUTPUT_SCHEMAS  # noqa: E402
from output_policy import step_artifact_path, report_paths  # noqa: E402

RULE_ID = "PhaseB-TestRule"

# Minimal valid payload per step — matches Phase A frozen contract
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
        "classification": {
            "status": "formalized",
            "evidence": ["clause present"],
            "defects": [],
        },
    },
    "step03_abstraction": {
        "status": "ok",
        "source_file_path": RULE_ID,
        "abstraction_summary": {
            "actor_map": ["Ship"],
            "variable_map": ["speed", "hasLight"],
            "naming_contract": {"reactiveclass": "PascalCase"},
        },
        "open_assumptions": [],
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
        "candidate_artifacts": [
            {
                "artifact_id": "cand-001",
                "model_path": f"output/work/{RULE_ID}/candidates/base.rebeca",
                "property_path": f"output/work/{RULE_ID}/candidates/base.property",
                "strategy": "base",
                "is_candidate": True,
                "confidence": 0.91,
                "mapping_path": "synthesis-agent",
            },
        ],
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
        "installation_report": [
            {
                "artifact_id": f"{RULE_ID}_model",
                "source_path": f"output/work/{RULE_ID}/candidates/base.rebeca",
                "dest_path": f"output/{RULE_ID}/{RULE_ID}.rebeca",
                "artifact_type": "model",
                "status": "promoted",
                "reason": None,
            },
        ],
    },
    "step08_reporting": {
        "status": "ok",
        "source_file_path": RULE_ID,
        "summary_path": f"output/reports/{RULE_ID}/summary.json",
        "summary_md_path": f"output/reports/{RULE_ID}/summary.md",
        "summary": {
            "total_rules": 1,
            "rules_passed": 1,
            "rules_failed": 0,
            "score_mean": 90.0,
        },
    },
}

# Map step artifact name → schema key
_STEP_SCHEMA_KEY = {
    "step01_init": "step01",
    "step02_triage": "step02",
    "step03_abstraction": "step03",
    "step04_mapping": "step04",
    "step05_candidates": "step05",
    "step06_verification_gate": "step06",
    "step07_packaging_manifest": "step07",
    "step08_reporting": "step08",
}


def _run_artifact_writer(rule_id: str, step: str, data: dict, base_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "artifact_writer.py"),
            "--rule-id", rule_id,
            "--step", step,
            "--data", json.dumps(data),
            "--base-dir", str(base_dir),
        ],
        capture_output=True,
        text=True,
    )


def _run_gate0(rule_id: str, base_dir: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(TESTS / "check_artifact_gaps.py"),
         "--rule-id", rule_id, "--base-dir", str(base_dir)],
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Tests: artifact_writer.py correctness
# ---------------------------------------------------------------------------

class TestArtifactWriterAtomicity:
    def test_writes_file_to_canonical_location(self, tmp_path: Path) -> None:
        data = STEP_PAYLOADS["step01_init"]
        result = _run_artifact_writer(RULE_ID, "step01_init", data, tmp_path)
        assert result.returncode == 0, result.stderr
        expected = step_artifact_path(RULE_ID, "step01_init", tmp_path)
        assert expected.exists()

    def test_written_file_is_valid_json(self, tmp_path: Path) -> None:
        data = STEP_PAYLOADS["step02_triage"]
        _run_artifact_writer(RULE_ID, "step02_triage", data, tmp_path)
        path = step_artifact_path(RULE_ID, "step02_triage", tmp_path)
        parsed = json.loads(path.read_text())
        assert parsed["status"] == "ok"

    def test_no_tmp_file_left_behind(self, tmp_path: Path) -> None:
        data = STEP_PAYLOADS["step03_abstraction"]
        _run_artifact_writer(RULE_ID, "step03_abstraction", data, tmp_path)
        work_dir = tmp_path / "work" / RULE_ID
        tmp_files = list(work_dir.glob("*.tmp"))
        assert tmp_files == [], f"Leftover .tmp files: {tmp_files}"

    def test_idempotent_rewrite(self, tmp_path: Path) -> None:
        """Running artifact_writer twice with same data produces identical output."""
        data = STEP_PAYLOADS["step04_mapping"]
        _run_artifact_writer(RULE_ID, "step04_mapping", data, tmp_path)
        path = step_artifact_path(RULE_ID, "step04_mapping", tmp_path)
        content_first = path.read_text()

        _run_artifact_writer(RULE_ID, "step04_mapping", data, tmp_path)
        content_second = path.read_text()

        assert json.loads(content_first) == json.loads(content_second)

    def test_invalid_step_name_exits_nonzero(self, tmp_path: Path) -> None:
        result = _run_artifact_writer(RULE_ID, "step99_bogus", {"status": "ok"}, tmp_path)
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# Tests: per-step schema validity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("step_artifact, schema_key", sorted(_STEP_SCHEMA_KEY.items()))
def test_step_payload_passes_schema(step_artifact: str, schema_key: str) -> None:
    """Each STEP_PAYLOADS entry must pass the Phase A frozen schema."""
    payload = copy.deepcopy(STEP_PAYLOADS[step_artifact])
    errors = validate_step_output(schema_key, payload)
    assert errors == [], f"{step_artifact}: schema violations: {errors}"


@pytest.mark.parametrize("step_artifact, schema_key", sorted(_STEP_SCHEMA_KEY.items()))
def test_artifact_written_and_read_back_passes_schema(
    step_artifact: str, schema_key: str, tmp_path: Path
) -> None:
    """Write via artifact_writer, read back from disk, validate schema — end-to-end."""
    data = STEP_PAYLOADS[step_artifact]
    result = _run_artifact_writer(RULE_ID, step_artifact, data, tmp_path)
    assert result.returncode == 0, result.stderr

    path = step_artifact_path(RULE_ID, step_artifact, tmp_path)
    on_disk = json.loads(path.read_text())
    errors = validate_step_output(schema_key, on_disk)
    assert errors == [], f"{step_artifact}: on-disk schema violations: {errors}"


# ---------------------------------------------------------------------------
# Tests: Gate 0 end-to-end (simulated complete pipeline run)
# ---------------------------------------------------------------------------

def _write_all_artifacts(base_dir: Path) -> None:
    """Simulate a complete pipeline run: write all 8 step artifacts."""
    for step_artifact, data in STEP_PAYLOADS.items():
        r = _run_artifact_writer(RULE_ID, step_artifact, data, base_dir)
        assert r.returncode == 0, f"artifact_writer failed for {step_artifact}: {r.stderr}"


def _create_report_files(base_dir: Path) -> None:
    """Create the four required report files under output/reports/<rule_id>/."""
    rp = report_paths(RULE_ID, base_dir)
    rp.report_dir.mkdir(parents=True, exist_ok=True)
    rp.summary_json.write_text(json.dumps({"status": "ok"}))
    rp.summary_md.write_text("# Summary\n")
    rp.verification_json.write_text(json.dumps({"status": "ok"}))
    rp.quality_gates_json.write_text(json.dumps({"status": "ok"}))


class TestGate0EndToEnd:
    def test_complete_run_passes_gate0(self, tmp_path: Path) -> None:
        _write_all_artifacts(tmp_path)
        _create_report_files(tmp_path)
        report = _run_gate0(RULE_ID, tmp_path)
        assert report["gate_passed"], f"Gate 0 failed: {report['missing']}"
        assert report["gaps"] == 0
        assert report["present_count"] == 8

    def test_missing_any_one_artifact_fails_gate0(self, tmp_path: Path) -> None:
        """Removing any single step artifact must cause Gate 0 to fail."""
        for step_artifact in STEP_PAYLOADS:
            with tempfile.TemporaryDirectory() as td:
                base = Path(td)
                _write_all_artifacts(base)
                _create_report_files(base)
                # Remove one artifact
                path = step_artifact_path(RULE_ID, step_artifact, base)
                path.unlink()
                report = _run_gate0(RULE_ID, base)
                assert not report["gate_passed"], (
                    f"Gate 0 should fail when {step_artifact} is missing"
                )

    def test_skeleton_artifacts_fail_gate0(self, tmp_path: Path) -> None:
        """Artifacts that only contain {'status':'ok'} must not pass Gate 0."""
        work_dir = tmp_path / "work" / RULE_ID
        work_dir.mkdir(parents=True)
        for step_artifact in STEP_PAYLOADS:
            p = work_dir / f"{step_artifact}.json"
            p.write_text(json.dumps({"status": "ok"}))
        report = _run_gate0(RULE_ID, tmp_path)
        assert not report["gate_passed"]
        assert report["gaps"] == 8

    def test_missing_report_files_fails_gate0(self, tmp_path: Path) -> None:
        """step08_reporting.json present but report files absent → Gate 0 fails."""
        _write_all_artifacts(tmp_path)
        # Deliberately do NOT call _create_report_files
        report = _run_gate0(RULE_ID, tmp_path)
        assert not report["gate_passed"]
        missing_files = {m["file"] for m in report["missing"]}
        assert "summary.json" in missing_files
        assert "quality_gates.json" in missing_files

    def test_rerun_produces_same_artifacts(self, tmp_path: Path) -> None:
        """Writing all artifacts twice produces identical on-disk content (idempotent)."""
        _write_all_artifacts(tmp_path)
        _create_report_files(tmp_path)
        snapshots_first = {}
        for step_artifact in STEP_PAYLOADS:
            path = step_artifact_path(RULE_ID, step_artifact, tmp_path)
            snapshots_first[step_artifact] = json.loads(path.read_text())

        # Second run
        _write_all_artifacts(tmp_path)
        for step_artifact in STEP_PAYLOADS:
            path = step_artifact_path(RULE_ID, step_artifact, tmp_path)
            assert json.loads(path.read_text()) == snapshots_first[step_artifact], (
                f"{step_artifact}: artifact changed on rerun"
            )


# ---------------------------------------------------------------------------
# Tests: Step06 FSM guard fields explicitly
# ---------------------------------------------------------------------------

class TestStep06FsmGuardFields:
    """step06_verification_gate.json must support all three FSM transition predicates."""

    def test_all_fsm_guard_fields_present(self, tmp_path: Path) -> None:
        data = STEP_PAYLOADS["step06_verification_gate"]
        _run_artifact_writer(RULE_ID, "step06_verification_gate", data, tmp_path)
        path = step_artifact_path(RULE_ID, "step06_verification_gate", tmp_path)
        on_disk = json.loads(path.read_text())
        assert "verified" in on_disk
        assert "vacuity_status" in on_disk and "is_vacuous" in on_disk["vacuity_status"]
        assert "mutation_score" in on_disk

    def test_failing_gate_payload_is_schema_valid(self) -> None:
        """A verification-failure payload (verified=False) must also be schema-valid."""
        failing = {
            "status": "ok",
            "source_file_path": RULE_ID,
            "verified": False,
            "rmc_exit_code": 1,
            "vacuity_status": {"is_vacuous": False},
            "mutation_score": 0.0,
        }
        assert validate_step_output("step06", failing) == []
