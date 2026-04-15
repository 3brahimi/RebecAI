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

