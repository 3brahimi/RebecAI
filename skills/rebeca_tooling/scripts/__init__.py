import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def _lazy_import(name, module_name):
    module = importlib.import_module(module_name)
    return getattr(module, name)

download_rmc = _lazy_import("download_rmc", "download-rmc")
is_valid_jar = _lazy_import("is_valid_jar", "download-rmc")
run_rmc = _lazy_import("run_rmc", "run-rmc")
install_artifacts = _lazy_import("install_artifacts", "install-artifacts")
verify_installation = _lazy_import("verify_installation", "verify-installation")
pre_run_rmc_check = _lazy_import("pre_run_rmc_check", "pre-run-rmc-check")
RuleStatusClassifier = _lazy_import("RuleStatusClassifier", "classify-rule-status")
COLREGFallbackMapper = _lazy_import("COLREGFallbackMapper", "colreg-fallback-mapper")
extract_legata_signals = _lazy_import("extract_signals", "classify-rule-status")
extract_colreg_signals = _lazy_import("extract_signals", "colreg-fallback-mapper")
from .utils import safe_path, safe_open, validate_https_url, resolve_executable
MutationEngine = _lazy_import("MutationEngine", "mutation-engine")
Mutation = _lazy_import("Mutation", "mutation-engine")
check_vacuity = _lazy_import("check_vacuity", "vacuity-checker")
extract_precondition = _lazy_import("extract_precondition", "vacuity-checker")
build_negated_property = _lazy_import("build_negated_property", "vacuity-checker")
capture_snapshot = _lazy_import("capture_snapshot", "snapshotter")
detect_hallucinations = _lazy_import("detect_hallucinations", "symbol-differ")
HallucinationResult = _lazy_import("HallucinationResult", "symbol-differ")

__all__ = [
    "download_rmc", "is_valid_jar", "run_rmc", "install_artifacts", "verify_installation",
    "pre_run_rmc_check", "RuleStatusClassifier", "COLREGFallbackMapper", "extract_legata_signals", "extract_colreg_signals",
    "safe_path", "safe_open", "validate_https_url", "resolve_executable",
    "MutationEngine", "Mutation", "check_vacuity", "extract_precondition",
    "build_negated_property", "capture_snapshot", "detect_hallucinations", "HallucinationResult"
]
from .transformation_utils import get_canonical_assertion, format_rebeca_define
