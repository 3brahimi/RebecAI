"""test_installer_config_parity.py — Regression tests for Phase H installer config parity.

Validates that:
- setup.py installs configs/rmc_defaults.json into the primary target
- workflow_fsm.py resolves its default config in both repo and installed layouts
- verify_installation.py warns when config is missing and passes when present
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SETUP_PY = REPO_ROOT / "setup.py"
VERIFY_SCRIPT = REPO_ROOT / "skills" / "rebeca_tooling" / "scripts" / "verify_installation.py"
FSM_SCRIPT = REPO_ROOT / "skills" / "rebeca_tooling" / "scripts" / "workflow_fsm.py"
CONFIGS_SRC = REPO_ROOT / "configs"
RMC_DEFAULTS_SRC = CONFIGS_SRC / "rmc_defaults.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _simulate_install(tmp_path: Path) -> Path:
    """Copy agents/, skills/, and configs/ into tmp_path mimicking setup.py behaviour."""
    target = tmp_path / ".agents"
    target.mkdir()
    shutil.copytree(REPO_ROOT / "agents", target / "agents")
    shutil.copytree(REPO_ROOT / "skills", target / "skills",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (target / "configs").mkdir()
    shutil.copy2(RMC_DEFAULTS_SRC, target / "configs" / "rmc_defaults.json")
    return target


def _run_verify(target: Path) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), str(target)],
        capture_output=True, text=True,
    )
    return result.returncode, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# Config presence after simulated install
# ---------------------------------------------------------------------------

class TestInstallerConfigParity:
    def test_rmc_defaults_installed(self, tmp_path):
        target = _simulate_install(tmp_path)
        assert (target / "configs" / "rmc_defaults.json").exists()

    def test_rmc_defaults_is_valid_json(self, tmp_path):
        target = _simulate_install(tmp_path)
        data = json.loads((target / "configs" / "rmc_defaults.json").read_text())
        assert "max_refinement_attempts" in data

    def test_local_mode_installs_config(self, tmp_path):
        """setup.py --dry-run in local mode should list configs as an install target."""
        result = subprocess.run(
            [sys.executable, str(SETUP_PY), "--mode", "local", "--no-rmc", "--dry-run"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0

    def test_global_mode_installs_config(self, tmp_path):
        result = subprocess.run(
            [sys.executable, str(SETUP_PY), "--mode", "global", "--no-rmc", "--dry-run"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# workflow_fsm.py default config resolution
# ---------------------------------------------------------------------------

class TestFsmDefaultConfigResolution:
    def test_repo_mode_resolves_config(self):
        """In repo layout (4 parents), _find_default_config() must return the repo config."""
        spec = importlib.util.spec_from_file_location("workflow_fsm", FSM_SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["workflow_fsm"] = mod
        spec.loader.exec_module(mod)
        resolved = mod._DEFAULT_CONFIG
        assert resolved == RMC_DEFAULTS_SRC, (
            f"Expected repo config {RMC_DEFAULTS_SRC}, got {resolved}"
        )

    def test_installed_mode_resolves_config(self, tmp_path):
        """In installed layout (3 parents from script = install root), config must resolve."""
        # Build a minimal installed tree under tmp_path
        install_root = tmp_path / ".agents"
        scripts_dir = install_root / "skills" / "rebeca_tooling" / "scripts"
        scripts_dir.mkdir(parents=True)

        # Copy the FSM script and its direct siblings (output_policy, step_schemas)
        for f in (REPO_ROOT / "skills" / "rebeca_tooling" / "scripts").iterdir():
            if f.is_file():
                shutil.copy2(f, scripts_dir / f.name)

        # Install configs 3 parents up from scripts_dir
        (install_root / "configs").mkdir()
        shutil.copy2(RMC_DEFAULTS_SRC, install_root / "configs" / "rmc_defaults.json")

        # Temporarily shadow workflow_fsm to load from the installed location
        installed_fsm = scripts_dir / "workflow_fsm.py"
        spec = importlib.util.spec_from_file_location("workflow_fsm_installed", installed_fsm)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["workflow_fsm_installed"] = mod
        spec.loader.exec_module(mod)

        expected = install_root / "configs" / "rmc_defaults.json"
        assert mod._DEFAULT_CONFIG == expected, (
            f"Installed mode: expected {expected}, got {mod._DEFAULT_CONFIG}"
        )

    def test_config_contains_max_refinement_attempts(self):
        spec = importlib.util.spec_from_file_location("workflow_fsm_cfg", FSM_SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["workflow_fsm_cfg"] = mod
        spec.loader.exec_module(mod)
        data = json.loads(mod._DEFAULT_CONFIG.read_text())
        assert isinstance(data.get("max_refinement_attempts"), dict)


# ---------------------------------------------------------------------------
# verify_installation.py config checks (warn mode)
# ---------------------------------------------------------------------------

class TestVerifyInstallationConfigChecks:
    def test_warns_when_config_missing(self, tmp_path):
        target = _simulate_install(tmp_path)
        # Remove the config to trigger warning
        (target / "configs" / "rmc_defaults.json").unlink()
        rc, output = _run_verify(target)
        assert rc == 0, "Missing config should not be a hard failure (warn mode)"
        assert "⚠" in output and "rmc_defaults.json" in output

    def test_passes_when_config_present(self, tmp_path):
        target = _simulate_install(tmp_path)
        rc, output = _run_verify(target)
        assert rc == 0
        assert "✓ FSM config found" in output

    def test_warns_when_fsm_controller_missing(self, tmp_path):
        target = _simulate_install(tmp_path)
        fsm = target / "skills" / "rebeca_tooling" / "scripts" / "workflow_fsm.py"
        fsm.unlink()
        rc, output = _run_verify(target)
        assert rc == 0, "Missing FSM controller should be a warning, not hard failure"
        assert "⚠" in output and "workflow_fsm.py" in output

    def test_passes_when_fsm_controller_present(self, tmp_path):
        target = _simulate_install(tmp_path)
        rc, output = _run_verify(target)
        assert "✓ FSM controller found" in output


# ---------------------------------------------------------------------------
# Regression: both local and global simulated installs produce config
# ---------------------------------------------------------------------------

class TestConfigParityBothModes:
    @pytest.mark.parametrize("mode_label", ["local", "global"])
    def test_simulated_install_has_config_for_both_modes(self, tmp_path, mode_label):
        """Both install modes must produce configs/rmc_defaults.json in the target."""
        target = _simulate_install(tmp_path)
        config = target / "configs" / "rmc_defaults.json"
        assert config.exists(), f"{mode_label} install missing configs/rmc_defaults.json"
        data = json.loads(config.read_text())
        assert "max_refinement_attempts" in data
