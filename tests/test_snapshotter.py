"""Unit tests for snapshotter.py using exported scripts interface."""

import hashlib
import sys
import tempfile
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parents[1] / "skills" / "rebeca_tooling"
_SCRIPTS_DIR = _SKILL_ROOT / "scripts"
sys.path.insert(0, str(_SKILL_ROOT))
sys.path.insert(0, str(_SCRIPTS_DIR))

from skills.rebeca_tooling.scripts import capture_snapshot


MODEL_TEXT = """\
reactiveclass Ship(10) {
  statevars {
    int length;
    boolean hasLight;
  }
  Ship() {
    length = 60;
    hasLight = true;
  }
  msgsrv tick() {
    length = length + 1;
  }
}
main {
  Ship s1():();
}
"""

PROPERTY_TEXT = """\
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


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def test_capture_snapshot_hashes_and_full_content():
    with tempfile.TemporaryDirectory(dir=Path.home()) as td:
        base = Path(td)
        model = base / "model.rebeca"
        prop = base / "model.property"
        model.write_text(MODEL_TEXT, encoding="utf-8")
        prop.write_text(PROPERTY_TEXT, encoding="utf-8")

        snapshot = capture_snapshot(
            model_file=str(model),
            property_file=str(prop),
            rule_id="Rule-22",
        )

        assert snapshot["rule_id"] == "Rule-22"
        assert snapshot["golden"]["model"]["content"] == MODEL_TEXT
        assert snapshot["golden"]["property"]["content"] == PROPERTY_TEXT
        assert snapshot["golden"]["model"]["sha256"] == _sha256(MODEL_TEXT)
        assert snapshot["golden"]["property"]["sha256"] == _sha256(PROPERTY_TEXT)


def test_capture_snapshot_extracts_model_and_property_identifiers():
    with tempfile.TemporaryDirectory(dir=Path.home()) as td:
        base = Path(td)
        model = base / "model.rebeca"
        prop = base / "model.property"
        model.write_text(MODEL_TEXT, encoding="utf-8")
        prop.write_text(PROPERTY_TEXT, encoding="utf-8")

        snapshot = capture_snapshot(
            model_file=str(model),
            property_file=str(prop),
            rule_id="Rule-22",
        )

        state_vars = set(snapshot["golden"]["model"]["state_variables"])
        model_refs = set(snapshot["golden"]["model"]["model_references"])
        prop_ids = set(snapshot["golden"]["property"]["identifiers"])

        assert {"length", "hasLight"}.issubset(state_vars)
        assert "length" in model_refs
        assert "hasLight" in prop_ids
        assert "isLong" in prop_ids
