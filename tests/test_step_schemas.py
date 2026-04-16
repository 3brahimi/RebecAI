"""Tests for step-boundary contract validation helpers."""

from __future__ import annotations

import copy
import json

import pytest

from skills.rebeca_tooling.scripts import assert_step_output, validate_step_output


VALID_FIXTURES: dict[str, dict[str, object]] = {
    "step01": {
        "status": "ok",
        "rule_id": "Rule-22",
        "rmc_jar_path": "/tmp/rmc.jar",
        "snapshot_path": "/tmp/snapshot.json",
    },
    "step02": {
        "status": "ok",
        "routing": {"path": "normal"},
        "classification": {
            "status": "formalized",
            "evidence": ["clause found"],
            "defects": [],
        },
    },
    "step03": {
        "status": "ok",
        "actors": ["Ship"],
        "state_variables": ["speed"],
        "assertion_map": {"Rule22": "!isLong || lightOn"},
    },
    "step04": {
        "status": "ok",
        "model_artifact": {"path": "/tmp/model.rebeca"},
        "property_artifact": {"path": "/tmp/model.property"},
    },
    "step05": {
        "status": "ok",
        "candidates": [
            {"path": "/tmp/candidate.property", "confidence": 0.91, "mapping_path": "synthesis-agent"}
        ],
    },
    "step06": {
        "status": "ok",
        "verified": True,
        "exit_code": 0,
        "output_dir": "/tmp/verify-out",
    },
    "step07": {
        "status": "ok",
        "manifest": [
            {"src": "/tmp/model.rebeca", "dest": "/tmp/pkg/model.rebeca", "status": "copied"}
        ],
    },
    "step08": {
        "status": "ok",
        "report": {"total_rules": 10, "rules_passed": 9, "score_mean": 91.5},
    },
}


MISSING_REQUIRED_FIELD: dict[str, str] = {
    "step01": "rule_id",
    "step02": "routing",
    "step03": "assertion_map",
    "step04": "model_artifact",
    "step05": "candidates",
    "step06": "verified",
    "step07": "manifest",
    "step08": "report",
}


@pytest.mark.parametrize("step_id", sorted(VALID_FIXTURES))
def test_validate_step_output_accepts_valid_fixtures(step_id: str) -> None:
    payload = copy.deepcopy(VALID_FIXTURES[step_id])
    errors = validate_step_output(step_id=step_id, data=payload)
    assert errors == []


@pytest.mark.parametrize("step_id", sorted(VALID_FIXTURES))
def test_validate_step_output_rejects_missing_required_field(step_id: str) -> None:
    payload = copy.deepcopy(VALID_FIXTURES[step_id])
    payload.pop(MISSING_REQUIRED_FIELD[step_id], None)
    errors = validate_step_output(step_id=step_id, data=payload)
    assert errors


def test_assert_step_output_raises_machine_readable_envelope() -> None:
    payload = copy.deepcopy(VALID_FIXTURES["step01"])
    payload.pop("rule_id", None)
    with pytest.raises(ValueError) as exc_info:
        assert_step_output(step_id="step01", data=payload)
    envelope = json.loads(str(exc_info.value))
    assert envelope["error"] == "step_contract_violation"
    assert envelope["step"] == "step01"
    assert envelope["violations"]
