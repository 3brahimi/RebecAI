import subprocess
import json
import sys

def call_tool(tool_name: str, input_data: dict) -> dict:
    cmd = [
        sys.executable, 
        "skills/rebeca_tooling/scripts/cli_runner.py", 
        "--tool", tool_name, 
        "--input", json.dumps(input_data)
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return json.loads(proc.stderr)
    return json.loads(proc.stdout)

# Usage in agents/triage-agent.py:
# result = call_tool("triage", input_data)
# print(json.dumps(result))
