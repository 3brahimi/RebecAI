"""Phase G integration tests: Gate 0 as a subprocess integration boundary.

Distinct from Phase B (which validates artifact_writer.py output correctness),
Phase G validates check_artifact_gaps.py exit codes and JSON envelope fields:
- Exit code 0 exactly when gate_passed
- Exit code 1 exactly when any gap exists
- missing[].reason == "file_not_found" for absent files
- missing[].reason == "schema_invalid" + violations[] populated for bad schema
- missing[].reason starts with "json_decode_error:" for corrupt JSON
- step08 report-file gaps surface with file names in missing[]
- Identical artifact tree → identical JSON result across repeated invocations

No overlap with Phase B: Phase B tests write via artifact_writer.py;
Phase G writes directly and focuses on Gate 0 subprocess contracts.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

GATE0 = Path(__file__).parent / "check_artifact_gaps.py"
SCRIPTS = Path(__file__).parent.parent / "skills" / "rebeca_tooling" / "scripts"

sys.path.insert(0, str(SCRIPTS))
from output_policy import report_paths, step_artifact_path  # noqa: E402

RULE_ID = "PhaseG-Rule"

# All required step artifacts: (schema_key, artifact_filename, artifact_step_key)
REQUIRED_ARTIFACTS = [
    ("step01", "step01_init.json",               "step01_init"),
    ("step02", "step02_triage.json",             "step02_triage"),
    ("step03", "step03_abstraction.json",        "step03_abstraction"),
    ("step04", "step04_mapping.json",            "step04_mapping"),
    ("step05", "step05_candidates.json",         "step05_candidates"),
    ("step06", "step06_verification_gate.json",  "step06_verification_gate"),
    ("step07", "step07_packaging_manifest.json", "step07_packaging_manifest"),
    ("step08", "step08_reporting.json",          "step08_reporting"),
]

VALID_PAYLOADS: dict[str, dict] = {
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
            "artifact_id": "c1",
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(step_key: str, data: dict, base_dir: Path) -> Path:
    path = step_artifact_path(RULE_ID, step_key, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _write_all(base_dir: Path) -> None:
    for _, _, step_key in REQUIRED_ARTIFACTS:
        _write(step_key, VALID_PAYLOADS[step_key], base_dir)


def _write_report_files(base_dir: Path) -> None:
    rp = report_paths(RULE_ID, base_dir)
    rp.report_dir.mkdir(parents=True, exist_ok=True)
    for fname in ("summary.json", "summary.md", "verification.json", "quality_gates.json"):
        (rp.report_dir / fname).write_text("{}", encoding="utf-8")


def _run_gate0(base_dir: Path) -> tuple[int, dict]:
    """Run check_artifact_gaps.py; return (exit_code, parsed_json_report)."""
    result = subprocess.run(
        [sys.executable, str(GATE0), "--rule-id", RULE_ID, "--base-dir", str(base_dir)],
        capture_output=True, text=True,
    )
    return result.returncode, json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Positive path
# ---------------------------------------------------------------------------

class TestGate0PositivePath:
    def test_complete_valid_artifacts_exit_0(self, tmp_path: Path) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        code, report = _run_gate0(tmp_path)
        assert code == 0, f"Expected exit 0, got {code}. Missing: {report.get('missing')}"

    def test_complete_valid_artifacts_gate_passed_true(self, tmp_path: Path) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        _, report = _run_gate0(tmp_path)
        assert report["gate_passed"] is True

    def test_complete_valid_artifacts_gaps_zero(self, tmp_path: Path) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        _, report = _run_gate0(tmp_path)
        assert report["gaps"] == 0

    def test_complete_valid_artifacts_present_count_8(self, tmp_path: Path) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        _, report = _run_gate0(tmp_path)
        assert report["present_count"] == 8

    def test_complete_valid_artifacts_missing_list_empty(self, tmp_path: Path) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        _, report = _run_gate0(tmp_path)
        assert report["missing"] == []

    def test_stdout_is_parseable_json(self, tmp_path: Path) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        result = subprocess.run(
            [sys.executable, str(GATE0), "--rule-id", RULE_ID, "--base-dir", str(tmp_path)],
            capture_output=True, text=True,
        )
        parsed = json.loads(result.stdout)
        assert "gate_passed" in parsed
        assert "missing" in parsed
        assert "present" in parsed


# ---------------------------------------------------------------------------
# Negative path 1: missing required artifact
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("schema_key,filename,step_key", REQUIRED_ARTIFACTS)
class TestGate0MissingArtifact:
    def test_missing_artifact_exits_1(
        self, schema_key: str, filename: str, step_key: str, tmp_path: Path
    ) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        step_artifact_path(RULE_ID, step_key, tmp_path).unlink()
        code, _ = _run_gate0(tmp_path)
        assert code == 1, f"Expected exit 1 when {filename} is missing"

    def test_missing_artifact_gate_passed_false(
        self, schema_key: str, filename: str, step_key: str, tmp_path: Path
    ) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        step_artifact_path(RULE_ID, step_key, tmp_path).unlink()
        _, report = _run_gate0(tmp_path)
        assert report["gate_passed"] is False

    def test_missing_artifact_reason_file_not_found(
        self, schema_key: str, filename: str, step_key: str, tmp_path: Path
    ) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        step_artifact_path(RULE_ID, step_key, tmp_path).unlink()
        _, report = _run_gate0(tmp_path)
        missing_reasons = {m["file"]: m["reason"] for m in report["missing"]}
        assert filename in missing_reasons, f"{filename} not in missing list"
        assert missing_reasons[filename] == "file_not_found"

    def test_missing_artifact_correct_file_named(
        self, schema_key: str, filename: str, step_key: str, tmp_path: Path
    ) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        step_artifact_path(RULE_ID, step_key, tmp_path).unlink()
        _, report = _run_gate0(tmp_path)
        missing_files = [m["file"] for m in report["missing"]]
        assert filename in missing_files


# ---------------------------------------------------------------------------
# Negative path 2: schema-invalid artifact (skeleton {"status":"ok"})
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("schema_key,filename,step_key", REQUIRED_ARTIFACTS)
class TestGate0SchemaInvalid:
    def test_skeleton_artifact_exits_1(
        self, schema_key: str, filename: str, step_key: str, tmp_path: Path
    ) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        step_artifact_path(RULE_ID, step_key, tmp_path).write_text(
            json.dumps({"status": "ok"}), encoding="utf-8"
        )
        code, _ = _run_gate0(tmp_path)
        assert code == 1

    def test_skeleton_artifact_reason_schema_invalid(
        self, schema_key: str, filename: str, step_key: str, tmp_path: Path
    ) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        step_artifact_path(RULE_ID, step_key, tmp_path).write_text(
            json.dumps({"status": "ok"}), encoding="utf-8"
        )
        _, report = _run_gate0(tmp_path)
        missing_entry = next(
            (m for m in report["missing"] if m["file"] == filename), None
        )
        assert missing_entry is not None, f"{filename} not in missing list"
        assert missing_entry["reason"] == "schema_invalid"

    def test_skeleton_artifact_violations_populated(
        self, schema_key: str, filename: str, step_key: str, tmp_path: Path
    ) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        step_artifact_path(RULE_ID, step_key, tmp_path).write_text(
            json.dumps({"status": "ok"}), encoding="utf-8"
        )
        _, report = _run_gate0(tmp_path)
        missing_entry = next(
            (m for m in report["missing"] if m["file"] == filename), None
        )
        assert missing_entry is not None
        assert "violations" in missing_entry
        assert len(missing_entry["violations"]) > 0


# ---------------------------------------------------------------------------
# Negative path 3: corrupt JSON
# ---------------------------------------------------------------------------

class TestGate0CorruptJson:
    def test_corrupt_json_exits_1(self, tmp_path: Path) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        step_artifact_path(RULE_ID, "step03_abstraction", tmp_path).write_text(
            "{ not valid json !!!", encoding="utf-8"
        )
        code, _ = _run_gate0(tmp_path)
        assert code == 1

    def test_corrupt_json_reason_starts_with_json_decode_error(self, tmp_path: Path) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        step_artifact_path(RULE_ID, "step03_abstraction", tmp_path).write_text(
            "{ not valid json !!!", encoding="utf-8"
        )
        _, report = _run_gate0(tmp_path)
        entry = next(
            (m for m in report["missing"] if m["file"] == "step03_abstraction.json"), None
        )
        assert entry is not None
        assert entry["reason"].startswith("json_decode_error:")


# ---------------------------------------------------------------------------
# Negative path 4: step08 report files missing
# ---------------------------------------------------------------------------

class TestGate0Step08ReportFiles:
    def test_step08_valid_but_no_report_files_exits_1(self, tmp_path: Path) -> None:
        _write_all(tmp_path)
        # Deliberately omit report files
        code, _ = _run_gate0(tmp_path)
        assert code == 1

    def test_step08_report_missing_names_correct_files(self, tmp_path: Path) -> None:
        _write_all(tmp_path)
        code, report = _run_gate0(tmp_path)
        missing_files = {m["file"] for m in report["missing"]}
        assert "summary.json" in missing_files
        assert "quality_gates.json" in missing_files

    @pytest.mark.parametrize("report_fname", [
        "summary.json", "summary.md", "verification.json", "quality_gates.json"
    ])
    def test_each_missing_report_file_individually_fails(
        self, report_fname: str, tmp_path: Path
    ) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        (report_paths(RULE_ID, tmp_path).report_dir / report_fname).unlink()
        code, report = _run_gate0(tmp_path)
        assert code == 1
        missing_files = {m["file"] for m in report["missing"]}
        assert report_fname in missing_files


# ---------------------------------------------------------------------------
# Determinism: repeated runs over unchanged artifacts yield identical JSON
# ---------------------------------------------------------------------------

class TestGate0Determinism:
    def test_repeated_runs_identical_json_on_complete_tree(self, tmp_path: Path) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        _, report1 = _run_gate0(tmp_path)
        _, report2 = _run_gate0(tmp_path)
        _, report3 = _run_gate0(tmp_path)
        assert report1 == report2 == report3

    def test_repeated_runs_identical_json_on_incomplete_tree(self, tmp_path: Path) -> None:
        _write_all(tmp_path)
        # Missing step05 and step07 — partial run
        step_artifact_path(RULE_ID, "step05_candidates", tmp_path).unlink()
        step_artifact_path(RULE_ID, "step07_packaging_manifest", tmp_path).unlink()
        _, report1 = _run_gate0(tmp_path)
        _, report2 = _run_gate0(tmp_path)
        assert report1 == report2

    def test_exit_code_stable_across_runs(self, tmp_path: Path) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        codes = [_run_gate0(tmp_path)[0] for _ in range(3)]
        assert all(c == 0 for c in codes)

    def test_gate_passed_field_stable_on_invalid_tree(self, tmp_path: Path) -> None:
        _write_all(tmp_path)
        # Skeleton step04 — always schema_invalid
        step_artifact_path(RULE_ID, "step04_mapping", tmp_path).write_text(
            json.dumps({"status": "ok"}), encoding="utf-8"
        )
        results = [_run_gate0(tmp_path)[1]["gate_passed"] for _ in range(3)]
        assert results == [False, False, False]


# ---------------------------------------------------------------------------
# Envelope structure validation
# ---------------------------------------------------------------------------

class TestGate0EnvelopeStructure:
    def test_report_contains_all_required_top_level_keys(self, tmp_path: Path) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        _, report = _run_gate0(tmp_path)
        for key in ("rule_id", "work_dir", "gaps", "present_count", "missing", "present",
                    "warnings", "gate_passed"):
            assert key in report, f"Missing top-level key: {key}"

    def test_rule_id_in_report_matches_input(self, tmp_path: Path) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        _, report = _run_gate0(tmp_path)
        assert report["rule_id"] == RULE_ID

    def test_present_entries_have_required_fields(self, tmp_path: Path) -> None:
        _write_all(tmp_path)
        _write_report_files(tmp_path)
        _, report = _run_gate0(tmp_path)
        for entry in report["present"]:
            assert "step" in entry
            assert "file" in entry
            assert "path" in entry

    def test_missing_entries_have_required_fields(self, tmp_path: Path) -> None:
        _write_all(tmp_path)
        # Remove one so there's a missing entry to inspect
        step_artifact_path(RULE_ID, "step02_triage", tmp_path).unlink()
        _, report = _run_gate0(tmp_path)
        for entry in report["missing"]:
            assert "step" in entry
            assert "file" in entry
            assert "path" in entry
            assert "reason" in entry

    def test_gaps_equals_len_missing(self, tmp_path: Path) -> None:
        _write_all(tmp_path)
        step_artifact_path(RULE_ID, "step01_init", tmp_path).unlink()
        step_artifact_path(RULE_ID, "step06_verification_gate", tmp_path).unlink()
        _, report = _run_gate0(tmp_path)
        assert report["gaps"] == len(report["missing"])
