"""Step boundary JSON schema validation helpers for the Step01→Step08 pipeline."""

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
    "step01": {
        "type": "object",
        "required": ["status", "rule_id", "rmc_jar_path", "snapshot_path"],
        "properties": {"status": {"type": "string"}, "rule_id": {"type": "string"}, "rmc_jar_path": {"type": "string"}, "snapshot_path": {"type": "string"}},
    },
    "step02": {
        "type": "object",
        "required": ["status", "routing", "classification"],
        "properties": {
            "status": {"type": "string"},
            "routing": {"type": "object"},
            "classification": {
                "type": "object",
                "required": ["status", "evidence", "defects"],
                "properties": {"status": {"type": "string"}, "evidence": {"type": "array"}, "defects": {"type": "array"}},
            },
        },
    },
    "step03": {
        "type": "object",
        "required": ["status", "actors", "state_variables", "assertion_map"],
        "properties": {"status": {"type": "string"}, "actors": {"type": "array"}, "state_variables": {"type": "array"}, "assertion_map": {"type": "object"}},
    },
    "step04": {
        "type": "object",
        "required": ["status", "model_artifact", "property_artifact"],
        "properties": {
            "status": {"type": "string"},
            "model_artifact": {"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}},
            "property_artifact": {"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}},
        },
    },
    "step05": {
        "type": "object",
        "required": ["status", "candidates"],
        "properties": {
            "status": {"type": "string"},
            "candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["path", "confidence", "mapping_path"],
                    "properties": {"path": {"type": "string"}, "confidence": {"type": "number"}, "mapping_path": {"type": "string"}},
                },
            },
        },
    },
    "step06": {
        "type": "object",
        "required": ["status", "verified", "exit_code", "output_dir"],
        "properties": {"status": {"type": "string"}, "verified": {"type": "boolean"}, "exit_code": {"type": "integer"}, "output_dir": {"type": "string"}},
    },
    "step07": {
        "type": "object",
        "required": ["status", "manifest"],
        "properties": {
            "status": {"type": "string"},
            "manifest": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["src", "dest", "status"],
                    "properties": {"src": {"type": "string"}, "dest": {"type": "string"}, "status": {"type": "string"}},
                },
            },
        },
    },
    "step08": {
        "type": "object",
        "required": ["status", "report"],
        "properties": {
            "status": {"type": "string"},
            "report": {
                "type": "object",
                "required": ["total_rules", "rules_passed", "score_mean"],
                "properties": {"total_rules": {"type": "integer"}, "rules_passed": {"type": "integer"}, "score_mean": {"type": "number"}},
            },
        },
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
