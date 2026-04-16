---
name: packaging_agent
description: |
  Step07 specialist for collecting pipeline artifacts, building a finalized
  manifest, and emitting a per-artifact installation report.
schema: skills/rebeca_tooling/schemas/packaging-agent.schema.json
skills:
  - rebeca_tooling
---

# Step07 Subagent: Packaging and Artifact Manifest

## Goal

Collect all artifacts produced by Step04 (model, property) and Step06
(RMC logs, compilation output), copy them to a destination directory,
and emit a structured manifest. Does NOT invoke `install_artifacts` —
that tool installs the framework itself, not pipeline outputs.

## Input Schema

| Field           | Type    | Required | Description                                              |
|-----------------|---------|----------|----------------------------------------------------------|
| `source_file_path`       | string  | yes      | Rule identifier (e.g. `Rule-22`)                         |
| `model_path`    | string  | yes      | Path to `.rebeca` model produced by Step04                |
| `property_path` | string  | yes      | Path to `.property` file produced by Step04               |
| `rmc_output_dir`| string  | yes      | Directory written by `run_rmc` in Step06                  |
| `dest_dir`      | string  | yes      | Destination directory for packaged artifacts             |
| `snapshot_path` | string  | no       | Optional Step01 snapshot file to include in package       |
| `dry_run`       | boolean | no       | If true, compute manifest but do not copy files (default false) |

## Artifact Collection Rules

1. **model** — `model_path` (`.rebeca` file from Step04)
2. **property** — `property_path` (`.property` file from Step04)
3. **logs** — all `*.log` files under `rmc_output_dir` (RMC stdout/stderr/compile logs)
4. **snapshot** — `snapshot_path` if provided and exists

Each artifact is tagged with one of:

| Status      | Meaning                                               |
|-------------|-------------------------------------------------------|
| `installed` | File copied to `dest_dir` successfully                |
| `skipped`   | Source does not exist (non-fatal; logged with reason) |
| `failed`    | Copy attempted and raised an exception                |

## Dest Dir Layout

```
{dest_dir}/
  {source_file_path}/
    model/    ← .rebeca file
    property/ ← .property file
    logs/     ← *.log files from rmc_output_dir
    snapshot/ ← snapshot JSON (if provided)
```

## Output Contract (success)

```json
{
  "status": "ok",
  "source_file_path": "Rule-22",
  "dest_dir": "/path/to/dest",
  "dry_run": false,
  "generated_files": [
    "/path/to/dest/Rule-22/model/Rule-22.rebeca",
    "/path/to/dest/Rule-22/property/Rule-22.property",
    "/path/to/dest/Rule-22/logs/rmc_stdout.log"
  ],
  "installation_report": [
    {
      "artifact_id": "Rule-22_model",
      "source_path": "/path/to/Rule-22.rebeca",
      "dest_path": "/path/to/dest/Rule-22/model/Rule-22.rebeca",
      "artifact_type": "model",
      "status": "installed",
      "reason": null
    },
    {
      "artifact_id": "Rule-22_snapshot",
      "source_path": "/path/to/snapshot.json",
      "dest_path": null,
      "artifact_type": "snapshot",
      "status": "skipped",
      "reason": "source file does not exist"
    }
  ]
}
```

## Error Envelope

```json
{
  "status":  "error",
  "phase":   "step07",
  "agent":   "packaging_agent",
  "message": "Human-readable description of failure"
}
```

Emit on: invalid/escaped paths, `dest_dir` creation failure, or schema
validation violation. Individual artifact copy failures do NOT trigger
an error envelope — they produce `status: "failed"` entries in the report.

## Output Patch (for coordinator)

- `workflow_summary.step07`
- `generated_files[]`
- `installation_report[]`
