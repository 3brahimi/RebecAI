---
name: rebeca-tooling
description: Cross-platform Python library for RMC operations, rule triage, scoring, and reporting
---

# Rebeca Tooling Skill

## Purpose

This skill provides a cross-platform Python library for all Rebeca model checking operations, including:
- RMC download and execution
- Shared RMC jar path resolution (`rmc_resolver`)
- Rule status classification and triage
- COLREG fallback mapping
- Vacuity analysis (`vacuity_checker`)
- Mutation generation and kill-run scoring (`mutation_engine`)
- Snapshot capture and symbol-level hallucination checks
- Single-rule scoring and aggregate reporting
- Per-rule comprehensive reporting (`generate_rule_report`)
- Multi-rule consolidation with publication-ready plots (`consolidate_reports`)
- Installation and verification utilities

## When to Use

Use this skill when you need to:
- Download or execute the RMC model checker
- Resolve/probe `rmc.jar` deterministically across local/global installs
- Classify Legata rule formalization status
- Generate provisional properties from COLREG text
- Run vacuity checks and feed vacuity outcomes into scoring
- Generate mutants and compute kill-rate mutation score with budget guardrails
- Compare model/property symbols against source artifacts for drift checks
- Score verification results
- Generate aggregate reports
- Generate comprehensive JSON/Markdown reports for an individual rule folder
- Consolidate many rule folders into one report with tables and bar/cactus plots (SVG+PNG)
- Install or verify toolchain artifacts

## Library Location

All Python modules are in `<scripts>`:
```bash
ls <scripts>
```

## Python Library Usage

### Import from Skill

```python
import sys
from pathlib import Path

# Add skill's lib to path
skill_path = Path("<skills>/rebeca_tooling").expanduser()
sys.path.insert(0, str(skill_path))

from scripts import (
    download_rmc,
    run_rmc,
    pre_run_rmc_check,
    resolve_rmc_jar,
    require_rmc_jar,
    RuleStatusClassifier,
    map_fallback
)
```

### RMC Operations

#### Download RMC

```python
from scripts import download_rmc

# Download latest release
result = download_rmc(
    url="https://github.com/rebeca-lang/org.rebecalang.rmc/releases/latest",
    dest_dir=".agents/rmc"
)

# Download specific version
result = download_rmc(
    url="https://github.com/rebeca-lang/org.rebecalang.rmc/releases",
    dest_dir=".agents/rmc",
    tag="2.14"
)

# Exit codes:
# 0: Success
# 1: Checksum mismatch
# 2: Download failed
```

#### Run RMC Verification

```python
from scripts import run_rmc

result = run_rmc(
    jar=<jar>,
    model="path/to/model.rebeca",
    property_file="path/to/property.property",
    output_dir="verification_output",
    timeout_seconds=120,
    jvm_opts=["-Xmx2g"]
)

# Exit codes:
# 0: Success (parse + compile)
# 1: Invalid inputs
# 3: Timeout
# 4: C++ compilation failed
# 5: Rebeca parse failed

# For semantic details, use run_rmc_detailed() from run_rmc.py directly:
# - model_out.outcome (runtime executable outcome)
# - result_artifact.outcome (parsed from exported result file when available)
# - verification_outcome (resolved semantic verdict)
```

#### Auto-Provision RMC

```python
from scripts import pre_run_rmc_check

# Ensures RMC is available, downloads if needed.
# Resolver precedence:
#   1) RMC_JAR
#   2) RMC_DESTINATION/rmc.jar
#   3) <jar>
result = pre_run_rmc_check()

# Exit codes:
# 0: RMC available
# 2: Download failed
```

### Rule Triage

#### Classify Rule Status

```python
from scripts import RuleStatusClassifier

classifier = RuleStatusClassifier()
result = classifier.classify("path/to/rule.legata")

# Returns dict with:
# - status: formalized|incomplete|incorrect|not-formalized|todo-placeholder
# - clause_count: number of clauses
# - evidence: list of findings
# - defects: list of defects
# - next_action: recommended action
```

#### COLREG Fallback Mapping

```python
from scripts import map_fallback

result = map_fallback(
    rule_id="Rule-99",
    colreg_text="Every vessel shall maintain a proper lookout"
)

# Returns dict with:
# - provisional_property: Rebeca property text
# - confidence: high|medium|low
# - assumptions: list of assumptions
# - requires_manual_review: bool
# - mapping_path: "colreg-fallback"
```

### Scoring and Reporting

#### Score Single Rule

```python
from scripts.score_single_rule import RubricScorer

scorer = RubricScorer()
scorecard = scorer.score_rule(
    rule_id="Rule-22",
    verify_status="pass",       # pass|fail|timeout|blocked|unknown
    model_artifact="model.rebeca",
    property_artifact="property.property",
    is_vacuous=False,           # from vacuity_checker result; None = unchecked
    assertion_id="Rule22",      # assertion label used in vacuity check
)

# Returns dict with:
# - score_total: 0-100
# - score_breakdown: {syntax:10, semantic_alignment:55, verification_outcome:25, hallucination_penalty:10}
# - status: Pass|Fail|Conditional|Blocked|Unknown
#   NOTE: a vacuous pass (is_vacuous=True) yields status=Conditional and score=85
# - confidence: 0.0-1.0
# - vacuity: {is_vacuous: bool|None, assertion_id: str|None, status: "non_vacuous"|"vacuous"|"unchecked"}
# - mapping_path: legata|colreg-fallback|synthesis-agent
# - failure_reasons: list
# - remediation_hints: list
```

## API/CLI Contract Sync (auto-generated source of truth)

To avoid doc drift, regenerate and review the live API/CLI contract directly from scripts:

```bash
python3 - <<'PY'
import importlib
from pathlib import Path

scripts = Path("<scripts>")
exports = importlib.import_module("skills.rebeca_tooling.scripts").__all__
print("# Exported symbols")
for name in sorted(exports):
    print(f"- {name}")

print("\n# CLI modules")
for p in sorted(scripts.glob("*.py")):
    if p.name in {"__init__.py", "utils.py"}:
        continue
    print(f"- {p.name}")
PY
```

Policy: if this generated list differs from SKILL.md examples, update SKILL.md in the same change.

#### Generate Aggregate Report

```python
from scripts.generate_report import ReportGenerator

generator = ReportGenerator()
generator.add_scorecard(scorecard)
generator.finalize()

Path("reports/").mkdir(parents=True, exist_ok=True)
with open("reports/summary.json", "w") as f:
    f.write(generator.to_json())
with open("reports/summary.md", "w") as f:
    f.write(generator.to_markdown())

# Outputs: reports/summary.json and reports/summary.md
# Use generate_report.py --output-dir to also emit verification.json and quality_gates.json.
```

#### Generate Per-Rule Comprehensive Report

```python
from pathlib import Path
from scripts.reporting_metrics import build_rule_report_bundle
from scripts.generate_rule_report import _build_report_payload, _render_markdown

rule_dir = Path("output/rules/Rule-22")
bundle = build_rule_report_bundle(rule_dir)
payload = _build_report_payload(bundle)

out_dir = rule_dir / "reports"
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "comprehensive_report.json").write_text(
  __import__("json").dumps(payload, indent=2),
  encoding="utf-8",
)
(out_dir / "comprehensive_report.md").write_text(
  _render_markdown(payload),
  encoding="utf-8",
)
```

#### Consolidate Multiple Rule Folders

```python
from pathlib import Path
from scripts.reporting_metrics import build_rule_report_bundle

root = Path("output/rules")
bundles = []
for child in root.iterdir():
  if child.is_dir():
    try:
      bundles.append(build_rule_report_bundle(child))
    except FileNotFoundError:
      # skip folders that are not completed rule artifacts
      pass

print(f"Loaded {len(bundles)} rule bundles for consolidation")
```

### Installation Utilities

#### Install Artifacts

```python
from scripts import install_artifacts

result = install_artifacts(
    target_root=".claude",
    mode="all"  # agent|skill|all
)

# Exit codes:
# 0: Success
# 1: Installation failed
```

#### Verify Installation

```python
from scripts import verify_installation

result = verify_installation(target_root=".claude")

# Exit codes:
# 0: All artifacts present
# 1: Missing artifacts
```

#### Complete Setup

Use `setup.py` at the repo root instead — it handles prerequisites, RMC download, artifact installation, and path patching in one step:

```bash
# Local install (.agents/ in CWD)
python3 setup.py

# Global install (~/.agents/)
python3 setup.py --mode global
```

## CLI Usage

All modules have command-line interfaces:

### RMC Operations

```bash
# Download RMC
python3 <scripts>/download_rmc.py \
  --url https://github.com/rebeca-lang/org.rebecalang.rmc/releases/latest \
  --dest-dir .agents/rmc

# Run verification
python3 <scripts>/run_rmc.py \
  --jar .agents/rmc/rmc.jar \
  --model model.rebeca \
  --property property.property \
  --output-dir output \
  --timeout-seconds 120 \
  --jvm-opt "-Xmx2g"

# Pre-run check
python3 <scripts>/pre_run_rmc_check.py
```

### Rule Triage

```bash
# Classify rule status
python3 <scripts>/classify_rule_status.py \
  --legata-path legata/Rule-22.legata \
  --output-json

# COLREG fallback mapping
python3 <scripts>/colreg_fallback_mapper.py \
  --rule-id Rule-99 \
  --colreg-text "Every vessel shall maintain a proper lookout" \
  --output-json
```

### Scoring and Reporting

```bash
# Score single rule — basic
python3 <scripts>/score_single_rule.py \
  --rule-id Rule-22 \
  --verify-status pass \
  --output-json

# Score with vacuity result (from vacuity_checker.py output):
#   --is-vacuous true|false        feed the is_vacuous field from check_vacuity()
#   --assertion-id Rule22          audit trail: which assertion was checked
# A vacuous pass downgrades status to Conditional (85/100).
python3 <scripts>/score_single_rule.py \
  --rule-id Rule-22 \
  --verify-status pass \
  --is-vacuous false \
  --assertion-id Rule22 \
  --output-json

# Vacuity check — use --assertion-id when multiple assertions exist
python3 <scripts>/vacuity_checker.py \
  --jar <jar> \
  --model model.rebeca \
  --property property.property \
  --output-dir output/Rule-22 \
  --assertion-id Rule22 \
  --output-json

# Generate report — accepts JSON array, NDJSON, or file path
# (a) from file
python3 <scripts>/generate_report.py \
  --input-scores scorecards.json \
  --output-dir reports/ \
  --format both

# (b) from single scorecard on stdin (NDJSON or JSON object)
python3 score_single_rule.py --rule-id Rule-22 --verify-status pass --output-json \
  | python3 <scripts>/generate_report.py

# Mutation generation only
python3 <scripts>/mutation_engine.py \
  --rule-id Rule-22 \
  --property property.property \
  --output-json

# Mutation + kill-run (executes mutants with RMC, reports killed/survived/score)
python3 <scripts>/mutation_engine.py \
  --rule-id Rule-22 \
  --model model.rebeca \
  --property property.property \
  --run-with-jar <jar> \
  --run-with-model model.rebeca \
  --run-with-property property.property \
  --run-timeout 60 \
  --max-mutants 50 \
  --total-timeout 600 \
  --seed 42 \
  --output-json

# kill_stats includes:
# total_generated, total_run, sampled, sample_seed,
# budget_exceeded, elapsed_seconds,
# killed, survived, errors, mutation_score, mutant_results

# Generate comprehensive per-rule report from a rule output folder
python3 <scripts>/generate_rule_report.py \
  --rule-dir output/rules/Rule-22
# default output: output/rules/reports/Rule-22/comprehensive_report.{json,md}

# Consolidate all rule folders and emit aggregate markdown/json + plots
python3 <scripts>/consolidate_reports.py \
  --root-dir output/rules \
  --output-dir output/reports

# Headless/CI mode if plot rendering is unavailable
python3 <scripts>/consolidate_reports.py \
  --root-dir output/rules \
  --output-dir output/reports \
  --skip-plots
```

### Installation

```bash
# Complete setup (use setup.py instead — see above)

# Install artifacts only
python3 <scripts>/install_artifacts.py \
  --target-root .claude \
  --mode all

# Verify installation
python3 <scripts>/verify_installation.py .claude
# --rmc-jar is accepted for backward compatibility (ignored; use pre_run_rmc_check.py for jar checks)
python3 <scripts>/verify_installation.py .claude --rmc-jar <jar>
```

## Platform Support

All modules work identically on:
- **Windows** (Python 3.8+ with g++/MinGW or WSL2)
- **macOS** (Python 3.8+ with Xcode Command Line Tools)
- **Linux** (Python 3.8+ with build-essential)

## Prerequisites

- Python 3.8+
- Java 11+ (for RMC)
- C++ compiler (g++ or clang, for RMC C++ compilation)

## Error Handling Pattern

```python
from scripts import run_rmc

def verify_rule(rule_id: str, model_path: str, property_path: str) -> dict:
    """Verify a single rule and return structured result."""
    output_dir = f"verification_output/{rule_id}"

    result = run_rmc(
        jar=".agents/rmc/rmc.jar",
        model=model_path,
        property_file=property_path,
        output_dir=output_dir,
        timeout_seconds=120
    )

    if result == 0:
        return {"rule_id": rule_id, "status": "verified"}
    elif result == 5:
        return {"rule_id": rule_id, "status": "syntax_error", "error_type": "rebeca_parse"}
    elif result == 4:
        return {"rule_id": rule_id, "status": "syntax_error", "error_type": "cpp_compile"}
    elif result == 3:
        return {"rule_id": rule_id, "status": "timeout"}
    else:
        return {"rule_id": rule_id, "status": "error", "exit_code": result}
```

## Module Reference

| Module | Purpose | CLI | Library | Exported |
|--------|---------|-----|---------|----------|
| `utils.py` | `safe_path`, `safe_open`, `validate_https_url`, `resolve_executable` — shared security guards | ✗ | ✓ | ✓ |
| `agent_utils.py` | Shared agent-facing helper functions | ✗ | ✓ | ✗ (use directly) |
| `cli_runner.py` | CLI subprocess orchestration helpers | ✗ | ✓ | ✗ (use directly) |
| `download_rmc.py` | Download RMC from GitHub; `is_valid_jar()` + `probe_rmc_jar()` | ✓ | ✓ | ✓ |
| `run_rmc.py` | Execute RMC model checker | ✓ | ✓ | ✓ |
| `rmc_result_parser.py` | Parse exported RMC/model.out result artifacts (XML/text) into normalized semantic outcomes | ✗ | ✓ | ✓ |
| `rmc_resolver.py` | Shared `rmc.jar` resolution (`resolve_rmc_jar`, `require_rmc_jar`) | ✗ | ✓ | ✓ |
| `pre_run_rmc_check.py` | Auto-provision RMC (magic-bytes + JVM probe); writes `rmc_path` marker | ✓ | ✓ | ✓ |
| `install_artifacts.py` | Install agent/skills | ✓ | ✓ | ✓ |
| `verify_installation.py` | Verify installation; `--rmc-jar` accepted for compat | ✓ | ✓ | ✓ |
| `classify_rule_status.py` | Rule status classification | ✓ | ✓ | ✓ |
| `colreg_fallback_mapper.py` | COLREG fallback mapping | ✓ | ✓ | ✓ |
| `vacuity_checker.py` | Vacuity check via negated-property RMC run; `--assertion-id` | ✓ | ✓ | ✓ |
| `mutation_engine.py` | Mutation generation + optional kill-run (`--run-with-jar/model/property`) | ✓ | ✓ | ✓ |
| `snapshotter.py` | Capture model/property snapshots and metadata | ✓ | ✓ | ✓ |
| `symbol_differ.py` | Detect symbol drift/hallucinations in generated artifacts | ✓ | ✓ | ✓ |
| `reporting_metrics.py` | Shared per-rule metrics extraction (score/mutation/vacuity/model/property/mapping deltas) | ✗ | ✓ | ✗ (use directly) |
| `score_single_rule.py` | 100-point scoring rubric; `--is-vacuous`, `--assertion-id` | ✓ | ✓ | ✗ (use directly) |
| `generate_report.py` | Aggregate reporting; `--input-scores` (JSON array/NDJSON/file); `finalize()` computes all metrics | ✓ | ✓ | ✗ (use directly) |
| `generate_rule_report.py` | Per-rule comprehensive report (`comprehensive_report.json/.md`) from a rule artifact directory | ✓ | ✓ | ✗ (use directly) |
| `consolidate_reports.py` | Multi-rule consolidation + tables + status/score/mutation/cactus plots (SVG+PNG) | ✓ | ✓ | ✗ (use directly) |
| `step_schemas.py` | Structured step output schema validation | ✗ | ✓ | ✓ |
| `transformation_utils.py` | Rule/property transformation utilities | ✗ | ✓ | ✗ (use directly) |
| `output_policy.py` | Canonical path policy for all pipeline outputs — the only permitted source of artifact paths | ✗ | ✓ | ✓ |
| `artifact_writer.py` | Atomically persist a step's JSON output to its canonical path (tmp→rename); required after every step | ✓ | ✓ | ✗ (use directly) |
| `check_artifact_gaps.py` | Gate 0 machine check — exits 0 only when all 8 step artifacts are present and schema-valid | ✓ | ✓ | ✗ (use directly) |
| `workflow_fsm.py` | Deterministic FSM controller — reads artifacts, evaluates predicates, emits one JSON action to stdout | ✓ | ✓ | ✗ (use directly) |
| `run_pipeline.py` | Feature-flagged executor loop (`FSM_CONTROLLER_ENABLED=1`); drives full pipeline via `workflow_fsm.py` | ✓ | ✓ | ✗ (use directly) |
| `shadow_compare.py` | Parity comparison between two completed runs — artifact presence and schema validity | ✓ | ✓ | ✗ (use directly) |
| `cleanup_outputs.py` | Remove scratch work directories while preserving promoted finals and reports | ✓ | ✓ | ✗ (use directly) |

## JSON Output Purity Contract

For every script supporting `--output-json`:
- **stdout** must contain JSON only (no logs/progress text)
- human-readable diagnostics/progress belong on **stderr**
- this contract is regression-tested in `tests/test_json_purity_cli.py`

When chaining scripts in pipelines, prefer JSON-mode everywhere:

```bash
python3 <scripts>/classify_rule_status.py \
  --legata-path legata/Rule-22.legata \
  --output-json
```

## Docs/CLI Drift Guardrail

Use the sync validator before releasing doc changes:

```bash
python3 scripts/validate-cli-help-sync.py
```

CI also runs this automatically via `.github/workflows/cli-help-doc-sync.yml`.

## Best Practices

1. **Always use pre_run_rmc_check()** before calling run_rmc() to ensure RMC is available
2. **Check exit codes** - Don't assume success, handle all error cases
3. **Use absolute paths** - Avoid relative paths for jar, model, and property files
4. **Set appropriate timeouts** - Complex models may need >120s
5. **Handle C++ compilation failures** - Exit code 4 means g++ failed, not RMC
6. **Distinguish parse vs compile errors** - Exit code 5 (parse) vs 4 (compile)
7. **Review fallback mappings** - COLREG fallback always requires manual review
8. **Always pass `--assertion-id` to vacuity_checker** when the property has more than one assertion — without it, the first assertion is used silently
9. **Feed vacuity result into score_single_rule** using `--is-vacuous` — a vacuous pass silently scores 100 otherwise
10. **Pipe scorecards as JSON array or NDJSON** to generate_report.py; do not rely on stdin line-by-line when cards span multiple lines
11. **Use generate_rule_report.py for artifact-rich per-rule outputs** instead of scorecard-only summaries when mutation/vacuity/model stats are required
12. **Use consolidate_reports.py for portfolio-level review** and include SVG plots for papers/decks, PNG for slides/CI artifacts

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `Invalid or corrupt jarfile` at JVM startup | Downloaded jar passes magic-bytes check but is corrupt | `pre_run_rmc_check.py` now auto-detects and re-downloads; delete stale jar and re-run |
| `verify_installation.py --rmc-jar ...` → unrecognized arg | Old doc pattern; `--rmc-jar` wasn't a flag | Flag now accepted (ignored); jar checks are `pre_run_rmc_check.py`'s responsibility |
| `rmc_path.txt` not found | Path marker written with `.txt` extension by third-party tooling | Resolver now probes both `rmc_path` and `rmc_path.txt` |
| `JSONDecodeError` piping pretty JSON to `generate_report.py` | Old main() was line-by-line only | Use `--input-scores file.json` or pipe a JSON array / NDJSON; both now accepted |
| Reports overwrite root `output/report.*` on each run | Flat output path | `generate_report.py --output-dir output` now writes nested `output/reports/<rule-id>/report.{json,md}` (single rule) or `output/reports/aggregate/` (multi-rule) |
| Report shows `rules_passed: 0` despite per-rule data | `finalize()` was a no-op | Fixed — `finalize()` now recomputes all aggregate fields from `per_rule_scorecards` |
| Vacuity result disagrees with scorecard | Each tool used a different assertion or different defaults | Pass `--assertion-id` to both `vacuity_checker.py` and `score_single_rule.py` |
| Mutation engine shows `mutation_score: 0` | Generation-only mode; mutants not executed | Add `--run-with-jar/model/property` flags to enable kill-run |

### Import Errors

If you get `ModuleNotFoundError`:
```python
# Ensure skill path is correct
skill_path = Path("<skills>/rebeca_tooling").expanduser()
print(f"Skill path exists: {skill_path.exists()}")
print(f"Scripts path exists: {(skill_path / 'scripts').exists()}")
```

### RMC Not Found

```python
from scripts import pre_run_rmc_check

# This will auto-download if missing
result = pre_run_rmc_check()
if result != 0:
    print("Failed to provision RMC")
```

### C++ Compilation Failures

Exit code 4 means g++ failed. Check:
```bash
g++ --version  # Ensure g++ is installed
```

Install if missing:
- Ubuntu/Debian: `sudo apt install build-essential`
- macOS: `xcode-select --install`
- Windows: Install MinGW or use WSL2