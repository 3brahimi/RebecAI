"""Integration tests for rebeca-hallucination orchestration behavior."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


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
    lightOn = (s1.hasLight == true);
  }
  Assertion {
    Rule22: !isLong || lightOn;
  }
}
"""

CURRENT_PROPERTY_WITH_REFERENCE_HALLUCINATION = """\
property {
  define {
    badRef = (s1.shadowState > 0);
  }
  Assertion {
    Rule22: badRef;
  }
}
"""


def test_orchestration_flow_snapshot_then_audit_clean_pass():
    with tempfile.TemporaryDirectory(dir=Path.home()) as td:
        base = Path(td)

        golden_model = base / "golden.rebeca"
        golden_prop = base / "golden.property"
        snapshot_json = base / "golden_snapshot.json"

        _write(golden_model, GOLDEN_MODEL)
        _write(golden_prop, GOLDEN_PROPERTY)

        snapshotter = Path(__file__).parents[1] / "skills" / "rebeca-tooling" / "scripts" / "snapshotter.py"
        differ = Path(__file__).parents[1] / "skills" / "rebeca-tooling" / "scripts" / "symbol_differ.py"

        snap_run = subprocess.run(
            [
                sys.executable,
                str(snapshotter),
                "--rule-id", "Rule-22",
                "--model", str(golden_model),
                "--property", str(golden_prop),
                "--output", str(snapshot_json),
            ],
            capture_output=True,
            text=True,
        )
        assert snap_run.returncode == 0
        assert snapshot_json.exists()

        audit_run = subprocess.run(
            [
                sys.executable,
                str(differ),
                "--snapshot", str(snapshot_json),
                "--model", str(golden_model),
                "--property", str(golden_prop),
                "--rmc-exit-code", "0",
                "--output-json",
            ],
            capture_output=True,
            text=True,
        )

        assert audit_run.returncode == 0
        payload = json.loads(audit_run.stdout)
        assert payload["is_hallucination"] is False
        assert payload["hallucination_type"] == "none"
        assert payload["offending_symbols"] == []


def test_orchestration_flow_reference_hallucination_with_mocked_rmc_stderr():
    with tempfile.TemporaryDirectory(dir=Path.home()) as td:
        base = Path(td)

        golden_model = base / "golden.rebeca"
        golden_prop = base / "golden.property"
        current_prop = base / "current.property"
        snapshot_json = base / "golden_snapshot.json"
        stderr_log = base / "rmc_stderr.log"

        _write(golden_model, GOLDEN_MODEL)
        _write(golden_prop, GOLDEN_PROPERTY)
        _write(current_prop, CURRENT_PROPERTY_WITH_REFERENCE_HALLUCINATION)
        _write(stderr_log, "Error: Unknown variable shadowState at line 4")

        snapshotter = Path(__file__).parents[1] / "skills" / "rebeca-tooling" / "scripts" / "snapshotter.py"
        differ = Path(__file__).parents[1] / "skills" / "rebeca-tooling" / "scripts" / "symbol_differ.py"

        snap_run = subprocess.run(
            [
                sys.executable,
                str(snapshotter),
                "--rule-id", "Rule-22",
                "--model", str(golden_model),
                "--property", str(golden_prop),
                "--output", str(snapshot_json),
            ],
            capture_output=True,
            text=True,
        )
        assert snap_run.returncode == 0

        audit_run = subprocess.run(
            [
                sys.executable,
                str(differ),
                "--snapshot", str(snapshot_json),
                "--model", str(golden_model),
                "--property", str(current_prop),
                "--rmc-exit-code", "5",
                "--rmc-stderr-log", str(stderr_log),
                "--output-json",
            ],
            capture_output=True,
            text=True,
        )

        assert audit_run.returncode == 1
        payload = json.loads(audit_run.stdout)
        assert payload["is_hallucination"] is True
        assert payload["hallucination_type"] == "reference"
        assert "shadowState" in payload["offending_symbols"]
