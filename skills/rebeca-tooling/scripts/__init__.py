"""
Legata→Rebeca Toolchain Library

Cross-platform Python implementations of RMC tooling, installation, and setup scripts.
"""

from .download-rmc import download-rmc, is_valid_jar
from .run-rmc import run-rmc
from .install-artifacts import install-artifacts
from .verify-installation import verify-installation
from .pre_run-rmc_check import pre_run-rmc_check
from .classify-rule-status import RuleStatusClassifier
from .colreg-fallback-mapper import COLREGFallbackMapper
from .utils import safe_path, safe_open, validate_https_url, resolve_executable
from .mutation-engine import MutationEngine, Mutation
from .vacuity-checker import check_vacuity, extract_precondition, build_negated_property
from .snapshotter import capture_snapshot
from .symbol-differ import detect_hallucinations, HallucinationResult

__all__ = [
    "download-rmc",
    "is_valid_jar",
    "run-rmc",
    "install-artifacts",
    "verify-installation",
    "pre_run-rmc_check",
    "RuleStatusClassifier",
    "COLREGFallbackMapper",
    "safe_path",
    "safe_open",
    "validate_https_url",
    "resolve_executable",
    "MutationEngine",
    "Mutation",
    "check_vacuity",
    "extract_precondition",
    "build_negated_property",
    "capture_snapshot",
    "detect_hallucinations",
    "HallucinationResult",
]
