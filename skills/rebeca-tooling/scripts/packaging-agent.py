#!/usr/bin/env python3
"""
packaging-agent (WF-07): Artifact Collection, Manifest Generation, Installation Report

Collects pipeline artifacts (model, property, RMC logs, snapshot), copies them
to a structured destination directory, and emits a manifest with per-artifact
installation status.

NOTE: Does NOT use install_artifacts.py — that tool installs the RebecAI
framework itself (agents/skills → ~/.claude/). This agent packages rule-specific
pipeline outputs for downstream consumption.

Exit codes:
  0: Success — contract written to stdout
  1: Failure — error envelope written to stdout
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

