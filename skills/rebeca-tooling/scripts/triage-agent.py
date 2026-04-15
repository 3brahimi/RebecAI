#!/usr/bin/env python3
"""
triage-agent (WF-02): Clause Eligibility and Triage

Classifies a Legata rule's formalization status via RuleStatusClassifier,
routes it to the correct downstream path, and optionally generates a
COLREG-fallback provisional property.

Exit codes:
  0: Success — full contract written to stdout
  1: Failure — error envelope written to stdout
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

