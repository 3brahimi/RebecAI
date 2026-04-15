#!/usr/bin/env python3
"""
init-agent (WF-01): Toolchain and Inputs Initialization

Validates inputs, provisions RMC, pins toolchain metadata, and captures a
golden snapshot. Emits a JSON contract consumed by coordinator shared_state.step01.

Exit codes:
  0: Success — full contract written to stdout
  1: Failure — error envelope written to stdout
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

