#!/usr/bin/env python3
"""
llm-lane-agent (WF-06): LLM-Assisted Candidate Property Generation

Runs in parallel with WF-04 (mapping-agent) after WF-03 completes.
Generates two candidate formulations from the same abstraction_summary:

  Strategy 'base'     — same !condition || exclusion || assurance pattern as
                        WF-04, with per-actor queue sizing from statevar count.
  Strategy 'temporal' — wraps the base assertion in LTL { G(assertion); }
                        for temporal model checkers.

ALL outputs carry:
  mapping_path: "llm-lane"
  is_candidate: true   ← coordinator MUST route to WF-05 before promotion

Exit codes:
  0: Success — contract written to stdout
  1: Failure — error envelope written to stdout
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

