---
name: rebeca-hallucination
description: |
  State-aware hallucination detection suite for RebecaAI.
  Captures a golden snapshot (Step01), performs symbol-diff checks (Step06 Phase3),
  and classifies dead-code vs reference hallucinations with RMC parse-error correlation.
  Provides the integrity score component (−10 penalty) fed into Step08 scoring.
---

# rebeca-hallucination

## Purpose

This skill orchestrates a two-tier hallucination detection pipeline for Rebeca artifacts:

1. **Capture Golden State** (`snapshotter.py`)
2. **Audit Hallucinations** (`symbol_differ.py` + `run_rmc` stderr/exit-code signals)

It integrates with Step06 Phase3 and Step08 scoring to distinguish:
- real hallucinations (`dead_code`, `reference`)
- non-hallucination parse issues (`syntax`)

---

## When to invoke

| Trigger | Action |
|---|---|
| Before applying rule transformation updates | Capture golden snapshot |
| After transformation and RMC execution | Audit hallucinations using snapshot + current files |
| `run_rmc` exit code = 5 | Run tier-2 reference-hallucination classification |
| During integrity scoring gate | Use `is_hallucination` result to apply integrity penalty |

---

## Tier Logic

### Tier 1 — Dead-Code Hallucination
- Compare state variable definitions in golden vs current `.rebeca`
- Detect added variables that are **never referenced** in `msgsrv` logic or `.property` define/assertion
- Output type: `dead_code`

### Tier 2 — Reference Hallucination
- Active when `run_rmc` returns exit code `5`
- Parse `rmc_stderr.log` identifiers and correlate with property references
- If property references symbols absent from model state variables, classify as `reference`
- If parse failure has no symbol mismatch signal, classify as `syntax`

---

## JSON Output Contract

The hallucination audit emits:

```json
{
  "is_hallucination": true,
  "hallucination_type": "dead_code",
  "offending_symbols": ["ghostState"],
  "rmc_error_trace": "..."
}
```

Additional diagnostic fields:
- `tier1_dead_code_symbols`
- `tier2_reference_symbols`
- `rule_id`

---

## CLI Usage

### 1) Capture Golden Snapshot

```bash
python3 <scripts>/snapshotter.py \
  --rule-id Rule22 \
  --model models/rule22.rebeca \
  --property models/rule22.property \
  --output output/rule22_golden_snapshot.json
```

### 2) Audit Hallucinations

```bash
python3 <scripts>/symbol_differ.py \
  --snapshot output/rule22_golden_snapshot.json \
  --model output/rule22_current.rebeca \
  --property output/rule22_current.property \
  --rmc-exit-code 5 \
  --rmc-stderr-log output/verification/rmc_stderr.log \
  --output-json
```

---

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Pass (no hallucination detected) |
| 1 | Fail (hallucination detected or invalid input/runtime error) |

---

## Integration Pattern

```python
from scripts import capture_snapshot, detect_hallucinations

snapshot = capture_snapshot(model_file=gold_model, property_file=gold_prop, rule_id=rule_id)
# write snapshot to JSON, then after run_rmc:

result = detect_hallucinations(
    snapshot_path=snapshot_json,
    current_model=current_model,
    current_property=current_property,
    rmc_exit_code=rmc_exit_code,
    rmc_stderr_log=rmc_stderr_log,
)

# score integration
integrity_pass = not result.is_hallucination
```
