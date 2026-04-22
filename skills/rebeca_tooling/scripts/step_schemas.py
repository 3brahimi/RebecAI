"""Step boundary JSON schema validation helpers for the Step01→Step08 pipeline.

v2 schemas are aligned to the actual agent output contracts so artifacts written
to disk (via artifact_writer.py) pass validation without any field renaming.
"""

from __future__ import annotations

import json
from typing import Any

try:  # Optional dependency
    from jsonschema import validate as _jsonschema_validate
    from jsonschema.exceptions import SchemaError as _JSONSchemaSchemaError
    from jsonschema.exceptions import ValidationError as _JSONSchemaValidationError

    _HAS_JSONSCHEMA = True
except ImportError:  # pragma: no cover - exercised by fallback tests if dependency absent
    _HAS_JSONSCHEMA = False


STEP_OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    # Step03: abstraction — actor/variable namespace lock
    "step03": {
        "type": "object",
        "required": ["status", "abstraction_summary"],
        "properties": {
            "status": {"type": "string"},
            "abstraction_summary": {
                "type": "object",
                "required": ["actor_map", "variable_map"],
                "properties": {
                    "actor_map": {"type": "array"},
                    "variable_map": {"type": "array"},
                    "naming_contract": {"type": "object"},
                },
            },
        },
    },
    # Step04: mapping — model + property file generation
    "step04": {
        "type": "object",
        "required": ["status", "model_artifact", "property_artifact"],
        "properties": {
            "status": {"type": "string"},
            "model_artifact": {
                "type": "object",
                "required": ["path"],
                "properties": {"path": {"type": "string"}},
            },
            "property_artifact": {
                "type": "object",
                "required": ["path"],
                "properties": {"path": {"type": "string"}},
            },
        },
    },
    # Step05: synthesis — candidate artifact index
    "step05": {
        "type": "object",
        "required": ["status", "candidate_artifacts"],
        "properties": {
            "status": {"type": "string"},
            "candidate_artifacts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["model_path", "property_path", "is_candidate", "confidence", "mapping_path"],
                    "properties": {
                        "artifact_id": {"type": "string"},
                        "model_path": {"type": "string"},
                        "property_path": {"type": "string"},
                        "strategy": {"type": "string"},
                        "is_candidate": {"type": "boolean"},
                        "confidence": {"type": "number"},
                        "mapping_path": {"type": "string"},
                    },
                },
            },
        },
    },
    # Step06: verification gate — RMC + vacuity + mutation summary
    # All three fields (verified, vacuity_status.is_vacuous, mutation_score) are
    # required because the FSM transition guard evaluates all three.
    "step06": {
        "type": "object",
        "required": ["status", "verified", "rmc_exit_code", "vacuity_status", "mutation_score"],
        "properties": {
            "status": {"type": "string"},
            "verified": {"type": "boolean"},
            "rmc_exit_code": {"type": "integer"},
            "rmc_output_dir": {"type": "string"},
            "vacuity_status": {
                "type": "object",
                "required": ["is_vacuous"],
                "properties": {"is_vacuous": {"type": "boolean"}},
            },
            "mutation_score": {"type": "number"},
        },
    },
    # Step07: packaging — promotion lineage manifest
    "step07": {
        "type": "object",
        "required": ["status", "installation_report"],
        "properties": {
            "status": {"type": "string"},
            "installation_report": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["source_path", "dest_path", "status"],
                    "properties": {
                        "artifact_id": {"type": "string"},
                        "source_path": {"type": "string"},
                        "dest_path": {"type": "string"},
                        "artifact_type": {"type": "string"},
                        "status": {"type": "string"},
                        "reason": {"type": ["string", "null"]},
                    },
                },
            },
        },
    },
    # Step08: reporting — terminal aggregation pointer
    "step08": {
        "type": "object",
        "required": ["status", "summary_path", "summary"],
        "properties": {
            "status": {"type": "string"},
            "summary_path": {"type": "string"},
            "summary_md_path": {"type": "string"},
            "summary": {
                "type": "object",
                "required": ["total_rules", "rules_passed", "score_mean"],
                "properties": {
                    "total_rules": {"type": "integer"},
                    "rules_passed": {"type": "integer"},
                    "score_mean": {"type": "number"},
                },
            },
        },
    },
    # FSM Controller: next-action output
    "fsm_action": {
        "type": "object",
        "required": [
            "status",
            "current_state",
            "next_state",
            "action",
            "reason_code",
            "required_artifacts",
            "missing_artifacts",
        ],
        "additionalProperties": False,
        "properties": {
            "status": {"type": "string", "enum": ["ok", "error", "retry", "blocked"]},
            "current_state": {"type": "string"},
            "next_state": {"type": "string"},
            "action": {
                "type": "object",
                "required": ["type", "step", "agent", "inputs"],
                "additionalProperties": False,
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["run_step", "refine_step", "finish", "block", "skip", "error"],
                    },
                    "step": {
                        "type": "string",
                        "enum": [
                            "step03_abstraction",
                            "step04_mapping",
                            "step05_synthesis",
                            "step06_verification_gate",
                            "step07_packaging",
                            "step08_reporting",
                            "none",
                        ],
                    },
                    "agent": {
                        "type": "string",
                        "enum": [
                            "abstraction_agent",
                            "mapping_agent",
                            "synthesis_agent",
                            "verification_exec",
                            "packaging_exec",
                            "reporting_exec",
                            "none",
                        ],
                    },
                    "inputs": {"type": "object"},
                },
            },
            "reason_code": {"type": "string"},
            "required_artifacts": {"type": "array", "items": {"type": "string"}},
            "missing_artifacts": {"type": "array", "items": {"type": "string"}},
        },
        "allOf": [
            {
                "if": {"properties": {"action": {"properties": {"type": {"const": "refine_step"}}}}},
                "then": {
                    "properties": {
                        "action": {
                            "properties": {
                                "inputs": {
                                    "required": [
                                        "prior_artifact_path",
                                        "issue_class",
                                        "issue_detail",
                                        "attempt_index",
                                        "budget_remaining",
                                    ]
                                }
                            }
                        }
                    }
                },
            },
            {
                "if": {"properties": {"action": {"properties": {"type": {"enum": ["finish", "block", "skip"]}}}}},
                "then": {"properties": {"action": {"properties": {"step": {"const": "none"}, "agent": {"const": "none"}}}}},
            },
        ],
    },
}


def _collect_required_key_errors(schema: dict[str, Any], data: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    required = schema.get("required", [])
    if isinstance(required, list):
        if not isinstance(data, dict):
            errors.append(f"{path}: expected object for required-key checks")
            return errors
        for key in required:
            if key not in data:
                errors.append(f"{path}.{key}: missing required key")
    properties = schema.get("properties", {})
    if isinstance(properties, dict) and isinstance(data, dict):
        for key, sub_schema in properties.items():
            if key in data and isinstance(sub_schema, dict):
                errors.extend(_collect_required_key_errors(sub_schema, data[key], f"{path}.{key}"))
    items = schema.get("items")
    if isinstance(items, dict) and isinstance(data, list):
        for index, item in enumerate(data):
            errors.extend(_collect_required_key_errors(items, item, f"{path}[{index}]"))
    return errors


def validate_step_output(step_id: str, data: dict[str, Any]) -> list[str]:
    """Validate one step output payload and return violations (empty list means valid)."""
    schema = STEP_OUTPUT_SCHEMAS.get(step_id)
    if schema is None:
        return [f"unknown-step: {step_id}"]
    if not isinstance(data, dict):
        return [f"{step_id}: payload must be a dict"]
    if _HAS_JSONSCHEMA:
        try:
            _jsonschema_validate(instance=data, schema=schema)
            return []
        except _JSONSchemaValidationError as exc:
            return [f"{step_id}: {exc.message}"]
        except _JSONSchemaSchemaError as exc:
            return [f"{step_id}: invalid-schema: {exc.message}"]
    return list(_collect_required_key_errors(schema, data, path=step_id))


def assert_step_output(step_id: str, data: dict[str, Any]) -> None:
    """Raise ValueError with machine-readable envelope when validation fails."""
    violations = validate_step_output(step_id=step_id, data=data)
    if violations:
        envelope = {
            "error": "step_contract_violation",
            "step": step_id,
            "violations": violations,
        }
        raise ValueError(json.dumps(envelope, sort_keys=True))
