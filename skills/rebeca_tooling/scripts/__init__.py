import importlib
import sys
from pathlib import Path

# Add scripts directory to path to support dynamic import
sys.path.insert(0, str(Path(__file__).parent))

def _lazy_import(name, module_name):
    # Filenames are hyphenated, modules must be underscore for Python
    module = importlib.import_module(module_name.replace("-", "_"))
    return getattr(module, name)

download_rmc = _lazy_import("download_rmc", "download-rmc")
is_valid_jar = _lazy_import("is_valid_jar", "download-rmc")
probe_rmc_jar = _lazy_import("probe_rmc_jar", "download-rmc")
run_rmc = _lazy_import("run_rmc", "run-rmc")
install_artifacts = _lazy_import("install_artifacts", "install-artifacts")
verify_installation = _lazy_import("verify_installation", "verify-installation")
pre_run_rmc_check = _lazy_import("pre_run_rmc_check", "pre-run-rmc-check")
resolve_rmc_jar = _lazy_import("resolve_rmc_jar", "rmc_resolver")
require_rmc_jar = _lazy_import("require_rmc_jar", "rmc_resolver")
RuleStatusClassifier = _lazy_import("RuleStatusClassifier", "classify-rule-status")
map_fallback = _lazy_import("map_fallback", "colreg-fallback-mapper")
from .utils import safe_path, safe_open, validate_https_url, resolve_executable
from .step_schemas import assert_step_output, validate_step_output
MutationEngine = _lazy_import("MutationEngine", "mutation-engine")
Mutation = _lazy_import("Mutation", "mutation-engine")
check_vacuity = _lazy_import("check_vacuity", "vacuity-checker")
extract_precondition = _lazy_import("extract_precondition", "vacuity-checker")
build_negated_property = _lazy_import("build_negated_property", "vacuity-checker")
capture_snapshot = _lazy_import("capture_snapshot", "snapshotter")
detect_hallucinations = _lazy_import("detect_hallucinations", "symbol-differ")
HallucinationResult = _lazy_import("HallucinationResult", "symbol-differ")

__all__ = [
    "download_rmc", "is_valid_jar", "probe_rmc_jar", "run_rmc", "install_artifacts", "verify_installation",
    "pre_run_rmc_check", "resolve_rmc_jar", "require_rmc_jar", "RuleStatusClassifier", "map_fallback",
    "assert_step_output", "validate_step_output",
    "safe_path", "safe_open", "validate_https_url", "resolve_executable",
    "MutationEngine", "Mutation", "check_vacuity", "extract_precondition",
    "build_negated_property", "capture_snapshot", "detect_hallucinations", "HallucinationResult"
]
