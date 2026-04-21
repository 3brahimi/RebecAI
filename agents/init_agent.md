---
name: init_agent
description: |
  Step01 specialist: validates inputs, records pinned toolchain versions,
  and captures a golden snapshot. Emits a JSON contract into coordinator shared_state.step01.
skills:
  - rebeca_tooling
---

# init_agent (Step01): Toolchain and Inputs Initialization

Validates that input files exist, records pinned RMC and Python versions, and captures a
golden snapshot for downstream verification.

## Inputs (from `action.inputs`)

- `rule_id` — rule identifier (e.g. `Rule-22`)
- `model` — path to `.rebeca` model file
- `property` — path to `.property` file
- `snapshot_out` — destination path for the snapshot JSON

## Invocation

```bash
python <scripts>/init_agent.py \
  --rule-id      <rule_id> \
  --model        <model> \
  --property     <property> \
  --snapshot-out <snapshot_out>
```

Capture stdout as the step artifact JSON. Exit 0 = success, exit 1 = failure.

## Output Contract (success)

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

## Artifact Persistence

```bash
python <scripts>/artifact_writer.py \
  --rule-id <rule_id> --step step01_init \
  --data '<stdout_json>' --base-dir output
```

## Error Envelope (failure)

| Field     | Type   | Description                                       |
|-----------|--------|---------------------------------------------------|
| `status`  | string | Always `"error"`                                  |
| `phase`   | string | Workflow step key — `"step01"`                    |
| `agent`   | string | Always `"init_agent"`                             |
| `message` | string | Root-cause description; safe to surface to user   |

Propagate to the coordinator without retrying.
