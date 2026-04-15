"""Unit tests for symbol_differ tier logic and CLI exit-code behavior."""

import json
import subprocess
import sys
import tempfile
from unittest.mock import patch
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parents[1] / "skills" / "rebeca_tooling"
_SCRIPTS_DIR = _SKILL_ROOT / "scripts"
sys.path.insert(0, str(_SKILL_ROOT))
sys.path.insert(0, str(_SCRIPTS_DIR))

from skills.rebeca_tooling.scripts import capture_snapshot, detect_hallucinations


GOLDEN_MODEL = """\
reactiveclass Ship(10) {
  statevars {
    int length;
    boolean hasLight;
  }
  msgsrv tick() {
    length = length + 1;
  }
}
main {
  Ship s1():();
}
"""

GOLDEN_PROPERTY = """\
property {
  define {
    isLong = (s1.length > 50);
  }
  Assertion {
    Rule22: isLong;
  }
}
"""

DEAD_CODE_MODEL = """\
reactiveclass Ship(10) {
  statevars {
    int length;
    boolean hasLight;
    int ghostState;
  }
  msgsrv tick() {
    length = length + 1;
  }
}
main {
  Ship s1():();
}
"""

REFERENCE_BROKEN_PROPERTY = """\
property {
  define {
    badRef = (s1.ghostState > 0);
  }
  Assertion {
    Rule22: badRef;
  }
}
"""

SYNTAX_BROKEN_PROPERTY = """\
property {
  Assertion {
    Assertion: true
  }
}
"""


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


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

        with patch("skills.rebeca_tooling.scripts.symbol_differ.extract_model_logic_identifiers", return_value=set()):
            result = detect_hallucinations(
                snapshot_path=str(snapshot_path),
                current_model=str(curr_model),
                current_property=str(golden_prop),
                rmc_exit_code=0,
            )

        assert result.is_hallucination is True
        assert result.hallucination_type == "dead_code"
        assert "ghostState" in result.offending_symbols


def test_tier2_reference_vs_syntax_classification_with_mocked_rmc_log():
    with tempfile.TemporaryDirectory(dir=Path.home()) as td:
        base = Path(td)
        golden_model = base / "golden.rebeca"
        golden_prop = base / "golden.property"
        snapshot_path = base / "snapshot.json"

        _write(golden_model, GOLDEN_MODEL)
        _write(golden_prop, GOLDEN_PROPERTY)
        snapshot = capture_snapshot(str(golden_model), str(golden_prop), "Rule-22")
        _write(snapshot_path, json.dumps(snapshot))

        ref_prop = base / "ref_broken.property"
        stderr_ref = base / "rmc_ref_stderr.log"
        _write(ref_prop, REFERENCE_BROKEN_PROPERTY)
        _write(stderr_ref, "Error: Unknown variable ghostState at line 4")

        ref_result = detect_hallucinations(
            snapshot_path=str(snapshot_path),
            current_model=str(golden_model),
            current_property=str(ref_prop),
            rmc_exit_code=5,
            rmc_stderr_log=str(stderr_ref),
        )

        assert ref_result.is_hallucination is True
        assert ref_result.hallucination_type == "reference"
        assert "ghostState" in ref_result.offending_symbols

        syntax_prop = base / "syntax_broken.property"
        stderr_syntax = base / "rmc_syntax_stderr.log"
        _write(syntax_prop, SYNTAX_BROKEN_PROPERTY)
        _write(stderr_syntax, "Parse error: expected ';' before '}'")

        syntax_result = detect_hallucinations(
            snapshot_path=str(snapshot_path),
            current_model=str(golden_model),
            current_property=str(syntax_prop),
            rmc_exit_code=5,
            rmc_stderr_log=str(stderr_syntax),
        )

        assert syntax_result.is_hallucination is False
        assert syntax_result.hallucination_type == "syntax"


def test_symbol_differ_cli_exit_codes_match_skill_contract():
    with tempfile.TemporaryDirectory(dir=Path.home()) as td:
        base = Path(td)
        golden_model = base / "golden.rebeca"
        golden_prop = base / "golden.property"
        broken_prop = base / "broken.property"
        snapshot_path = base / "snapshot.json"
        stderr_ref = base / "rmc_ref_stderr.log"

        _write(golden_model, GOLDEN_MODEL)
        _write(golden_prop, GOLDEN_PROPERTY)
        _write(broken_prop, REFERENCE_BROKEN_PROPERTY)
        _write(stderr_ref, "Error: Unknown variable ghostState at line 4")

        snapshot = capture_snapshot(str(golden_model), str(golden_prop), "Rule-22")
        _write(snapshot_path, json.dumps(snapshot))

        script = Path(__file__).parents[1] / "skills" / "rebeca_tooling" / "scripts" / "symbol_differ.py"

        pass_run = subprocess.run(
            [
                sys.executable,
                str(script),
                "--snapshot", str(snapshot_path),
                "--model", str(golden_model),
                "--property", str(golden_prop),
                "--rmc-exit-code", "0",
            ],
            capture_output=True,
            text=True,
        )
        assert pass_run.returncode == 0

        fail_run = subprocess.run(
            [
                sys.executable,
                str(script),
                "--snapshot", str(snapshot_path),
                "--model", str(golden_model),
                "--property", str(broken_prop),
                "--rmc-exit-code", "5",
                "--rmc-stderr-log", str(stderr_ref),
            ],
            capture_output=True,
            text=True,
        )
        assert fail_run.returncode == 1
