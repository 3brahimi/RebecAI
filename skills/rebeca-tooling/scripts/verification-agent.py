#!/usr/bin/env python3
"""
verification-agent (WF-05): RMC Verification, Vacuity Check, Mutation Scoring

Orchestrates:
  1. run_rmc      — compile .rebeca + .property → exit code classification
  2. check_vacuity — vacuity check (only when rmc_exit_code == 0)
  3. MutationEngine — mutation scoring (only when rmc_exit_code == 0)

Exit codes:
  0: Success — full contract written to stdout
  1: Failure — error envelope written to stdout
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

