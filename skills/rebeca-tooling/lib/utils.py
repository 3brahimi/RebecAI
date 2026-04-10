#!/usr/bin/env python3
"""Shared utilities for the rebeca-tooling library."""

import sys
from pathlib import Path
from urllib.parse import urlparse

ALLOWED_BASE = Path.home()


def safe_path(p: str) -> Path:
    """
    Resolve and validate a user-supplied path stays within ALLOWED_BASE.

    Returns the resolved Path on success.
    Prints an error and exits with code 1 if the path escapes ALLOWED_BASE.
    """
    resolved = Path(p).expanduser().resolve()
    if not str(resolved).startswith(str(ALLOWED_BASE)):
        print(f"Error: path '{p}' resolves outside allowed base '{ALLOWED_BASE}'", file=sys.stderr)
        sys.exit(1)
    return resolved


def validate_https_url(url: str) -> None:
    """Raise ValueError if url is not a valid https URL."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"Unsafe URL scheme '{parsed.scheme}': only https is permitted")
    if not parsed.netloc:
        raise ValueError(f"Invalid URL (missing host): {url}")
