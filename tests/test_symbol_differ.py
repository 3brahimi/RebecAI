import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from skills.rebeca_tooling.scripts.symbol_differ import detect_hallucinations
from skills.rebeca_tooling.scripts.snapshotter import capture_snapshot

GOLDEN_MODEL = "reactiveclass Test(1) { statevars { int x; } Test() { x = 1; } main { Test t():(); } }"
GOLDEN_PROPERTY = "property { Assertion { Rule22: x > 0; } }"
DEAD_CODE_MODEL = "reactiveclass Test(1) { statevars { int unused; int x; } Test() { x = 1; } main { Test t():(); } }"

def _write(p: Path, c: str):
    p.write_text(c, encoding="utf-8")

def test_tier1_dead_code_hallucination_detection():
    with tempfile.TemporaryDirectory(dir=Path.home()) as td:
        base = Path(td)
        golden_model = base / "golden.rebeca"
        golden_prop = base / "golden.property"
        curr_model = base / "curr.rebeca"

        _write(golden_model, GOLDEN_MODEL)
        _write(golden_prop, GOLDEN_PROPERTY)
        _write(curr_model, DEAD_CODE_MODEL)

        snapshot = capture_snapshot(str(golden_model), str(golden_prop), "Rule-22")
        snapshot_path = base / "snapshot.json"
        _write(snapshot_path, json.dumps(snapshot))

        # We assume extract_model_logic_identifiers is now correctly imported from symbol_differ
        from skills.rebeca_tooling.scripts.symbol_differ import extract_model_logic_identifiers
        with patch("skills.rebeca_tooling.scripts.symbol_differ.extract_model_logic_identifiers", return_value={"x"}):
            result = detect_hallucinations(
                snapshot_path=str(snapshot_path),
                current_model=str(curr_model),
                current_property=str(golden_prop),
                rmc_exit_code=0,
            )

        assert result.is_hallucination is True
        assert "unused" in result.tier1_dead_code_symbols
