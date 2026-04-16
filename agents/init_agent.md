---
name: init_agent
description: 'Step01 specialist: validates inputs, provisions RMC, pins toolchain
  metadata,

  and captures a golden snapshot. Emits a JSON contract into coordinator shared_state.step01.

  '
---

# init_agent (Step01): Toolchain and Inputs Initialization

## Goal

Bootstrap a deterministic transformation session: verify files exist, ensure RMC is
available (downloading if needed), record pinned toolchain versions, and capture a
golden snapshot so downstream agents (`verification_agent`, `integrity_agent`) have a
tamper-evident baseline.

## Inputs (from coordinator `shared_state`)

| Field             | Type   | Required | Description                                          |
|-------------------|--------|----------|------------------------------------------------------|
| `source_file_path`         | string | yes      | Rule identifier, e.g. `Rule-22`                      |
| `model`           | string | yes      | Path to `.rebeca` model file                         |
| `property`        | string | yes      | Path to `.property` file                             |
| `snapshot_out`    | string | yes      | Destination path for the snapshot JSON               |
| `rmc_destination` | string | no       | Override RMC directory (env/marker used if omitted)  |

## Tasks (in order)

1. Validate that `model` and `property` exist and pass `safe_path()`.
2. Call `pre_run_rmc_check(rmc_destination)` — downloads RMC if missing.
3. Detect RMC version and record Python environment metadata.
4. Call `capture_snapshot(model, property, source_file_path)` — writes snapshot JSON to `snapshot_out`.
5. Emit success contract JSON to stdout; exit 0.

If any step fails, emit the **Error Envelope** (see below) to stdout and exit 1 immediately.

## CLI

```bash
python skills/rebeca_tooling/scripts/init_agent.py \
  --rule-id       Rule-22 \
  --model         output/Rule-22.rebeca \
  --property      output/Rule-22.property \
  --snapshot-out  output/snapshots/Rule-22.snapshot.json \
  [--rmc-destination ~/.rebeca/rmc]
```

Exit code `0` = success, `1` = failure.

## Output Contract (success)

Merged into coordinator `phase_results.step01`:

```json
{
  "status": "ok",
  "source_file_path": "Rule-22",
  "rmc": {
    "jar": "/abs/path/.rebeca/rmc/rmc.jar",
    "version": "2.15.0"
  },
  "python": {
    "version": "3.12.0 (main, ...)",
    "executable": "/usr/bin/python3"
  },
  "inputs": {
    "model":    "/abs/path/Rule-22.rebeca",
    "property": "/abs/path/Rule-22.property"
  },
  "snapshot_path": "/abs/path/output/snapshots/Rule-22.snapshot.json"
}
```

## Error Envelope (failure)

All failures from this agent conform to the canonical **Error Envelope** schema, which
is also the standard format across all sub_agents in this pipeline:

```json
{
  "status":  "error",
  "phase":   "step01",
  "agent":   "init_agent",
  "message": "Human-readable description of what failed"
}
```

| Field     | Type   | Description                                       |
|-----------|--------|---------------------------------------------------|
| `status`  | string | Always `"error"`                                  |
| `phase`   | string | Workflow step key (`"step01"` through `"step08"`) |
| `agent`   | string | Name of the failing agent                         |
| `message` | string | Root-cause description; safe to surface to user   |

The coordinator MUST NOT advance to Step02 when it receives this envelope.

## Failure Modes

| Condition                            | `message` prefix                           |
|--------------------------------------|--------------------------------------------|
| Model or property file not found     | `"Model file not found: …"`               |
| Path escapes `~` (`safe_path` error) | `"Invalid path: …"`                        |
| `pre_run_rmc_check` returns != 0     | `"pre_run_rmc_check failed (exit N): …"`  |
| `capture_snapshot` raises            | `"snapshotter failed: …"`                  |

## Implementation Notes

- Uses `skills/rebeca_tooling/scripts/` exclusively via its `__init__.py` exports.
- Temp files (if any) are written inside `Path.home()` to satisfy `safe_path()`.
- RMC version detection: tries `java -jar rmc.jar` with a 5 s timeout; extracts the
  first non-empty output line. Falls back to the jar filename stem (e.g. `rmc-2.15.0`).
- This agent is **idempotent**: re-running with the same inputs overwrites the snapshot
  JSON in place without side effects.
