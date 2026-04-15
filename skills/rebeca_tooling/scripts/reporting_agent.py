#!/usr/bin/env python3
"""
reporting-agent (WF-08): Aggregate Scoring Report Generation

Wraps ReportGenerator (generate_report.py) to consume per-rule scorecards
assembled by the coordinator, finalize aggregate metrics, and write
report.json + report.md to the designated output directory.

NOTE: Scoring (RubricScorer.score_rule) runs BEFORE this agent — the
coordinator passes finalized scorecards in. This agent only aggregates
and formats. ReportGenerator and RubricScorer are NOT exported from
skills/__init__.py; imported directly from generate_report.py.

Exit codes:
  0: Success — contract written to stdout
  1: Failure — error envelope written to stdout
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Canonical error envelope
# ---------------------------------------------------------------------------

def _error(message: str) -> Dict[str, Any]:
    return {"status": "error", "phase": "step08", "agent": "reporting-agent", "message": message}


# ---------------------------------------------------------------------------
# Stub entrypoint — implementation pending
# ---------------------------------------------------------------------------

def run_reporting(
    scorecards: List[Dict[str, Any]],
    output_dir: str,
) -> Tuple[Dict[str, Any], int]:
    """Execute WF-08 reporting pipeline. Returns (contract, exit_code)."""
    return _error("reporting-agent not yet implemented"), 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="reporting-agent (WF-08): aggregate scoring report generation"
    )
    parser.add_argument("--scorecards",  required=True, help="JSON array or @/abs/path/to/file")
    parser.add_argument("--output-dir",  required=True)
    args = parser.parse_args()

    raw = args.scorecards
    if raw.startswith("@"):
        scorecards = json.loads(Path(raw[1:]).read_text(encoding="utf-8"))
    else:
        scorecards = json.loads(raw)

    result, exit_code = run_reporting(scorecards, args.output_dir)
    print(json.dumps(result, indent=2))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

