"""Rigorous tests for the fsm_action JSON schema (conditional logic)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import validate
from jsonschema.exceptions import ValidationError

# Load the schema directly from the file to ensure we are testing the actual deliverable.
SCHEMA_PATH = Path("skills/rebeca_tooling/schemas/workflow-fsm-action.schema.json")
with SCHEMA_PATH.open("r", encoding="utf-8") as f:
    FSM_SCHEMA = json.load(f)

VALID_RUN_STEP = {
    "status": "ok",
    "current_state": "initialized",
    "next_state": "triaged",
    "action": {
        "type": "run_step",
        "step": "step02_triage",
        "agent": "triage_agent",
        "inputs": {"rule_id": "Rule-22"}
    },
    "reason_code": "artifact_missing",
    "required_artifacts": ["step02_triage.json"],
    "missing_artifacts": ["step02_triage.json"]
}

VALID_REFINE_STEP = {
    "status": "retry",
    "current_state": "abstracted",
    "next_state": "abstracted",
    "action": {
        "type": "refine_step",
        "step": "step03_abstraction",
        "agent": "abstraction_agent",
        "inputs": {
            "rule_id": "Rule-22",
            "prior_artifact_path": "output/work/Rule-22/step03_abstraction.json",
            "issue_class": "missing_actors",
            "issue_detail": "LLM failed to extract OwnShip",
            "attempt_index": 2,
            "budget_remaining": 1
        }
    },
    "reason_code": "abstraction_incomplete",
    "required_artifacts": ["step03_abstraction.json"],
    "missing_artifacts": []
}

VALID_FINISH = {
    "status": "ok",
    "current_state": "reported",
    "next_state": "none",
    "action": {
        "type": "finish",
        "step": "none",
        "agent": "none",
        "inputs": {}
    },
    "reason_code": "pipeline_complete",
    "required_artifacts": ["step08_reporting.json"],
    "missing_artifacts": []
}

def test_valid_run_step():
    validate(instance=VALID_RUN_STEP, schema=FSM_SCHEMA)

def test_valid_refine_step():
    validate(instance=VALID_REFINE_STEP, schema=FSM_SCHEMA)

def test_valid_finish():
    validate(instance=VALID_FINISH, schema=FSM_SCHEMA)

def test_refine_step_missing_inputs():
    """If action.type is refine_step, specific inputs are required."""
    invalid = copy.deepcopy(VALID_REFINE_STEP)
    # Remove one required refinement field
    invalid["action"]["inputs"].pop("issue_class")
    
    with pytest.raises(ValidationError) as exc_info:
        validate(instance=invalid, schema=FSM_SCHEMA)
    assert "'issue_class' is a required property" in str(exc_info.value)

def test_finish_requires_none_step_agent():
    """If action.type is finish, step and agent MUST be 'none'."""
    invalid = copy.deepcopy(VALID_FINISH)
    invalid["action"]["step"] = "step08_reporting"
    
    with pytest.raises(ValidationError) as exc_info:
        validate(instance=invalid, schema=FSM_SCHEMA)
    assert "'none' was expected" in str(exc_info.value)

def test_invalid_action_type():
    invalid = copy.deepcopy(VALID_RUN_STEP)
    invalid["action"]["type"] = "invalid_type"
    with pytest.raises(ValidationError):
        validate(instance=invalid, schema=FSM_SCHEMA)

def test_mismatched_enums():
    invalid = copy.deepcopy(VALID_RUN_STEP)
    invalid["action"]["step"] = "wrong_step_name"
    with pytest.raises(ValidationError):
        validate(instance=invalid, schema=FSM_SCHEMA)
