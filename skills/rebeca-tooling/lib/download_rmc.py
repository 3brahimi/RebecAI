#!/usr/bin/env python3
"""Download RMC from official GitHub releases with retry and checksum validation."""

import argparse
import hashlib
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse
from urllib.request import urlopen, Request

from utils import validate_https_url


def is_valid_jar(jar_path: Path) -> bool:
    """Check if file is a valid Java archive."""
    if not jar_path.exists():
        return False
    try:
        with open(jar_path, 'rb') as f:
            magic = f.read(4)
            return magic == b'PK\x03\x04'  # ZIP/JAR magic number
    except Exception:
        return False


def resolve_latest_release(base_url: str) -> Optional[str]:
    """Resolve latest release tag from GitHub."""
    ALLOWED_HOST = "github.com"
    ALLOWED_PATH_PREFIX = "/rebeca-lang/org.rebecalang.rmc/releases/tag/"
    try:
        validate_https_url(base_url)
        req = Request(base_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req) as response:
            final_url = response.geturl()
            # Validate the redirected URL is the expected GitHub releases endpoint
            # before extracting the tag, preventing open-redirect tag injection
            if not isinstance(final_url, str):
                print("Error: Unexpected URL type in response", file=sys.stderr)
                return None
            parsed = urlparse(final_url)
            if parsed.netloc != ALLOWED_HOST or not parsed.path.startswith(ALLOWED_PATH_PREFIX):
                print(f"Error: Redirected to unexpected URL: {final_url}", file=sys.stderr)
                return None
            match = re.search(r'/tag/([^/]+)$', parsed.path)
            return match.group(1) if match else None
    except Exception as e:
        print(f"Error resolving latest release: {e}", file=sys.stderr)
        return None


def download_file(url: str, dest_path: Path, retry_count: int = 3, retry_delay: int = 2) -> bool:
    """Download file with retry logic."""
    try:
        validate_https_url(url)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return False
    for attempt in range(1, retry_count + 1):
        try:
            print(f"Downloading RMC (attempt {attempt}/{retry_count})...")
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req) as response:
                with open(dest_path, 'wb') as f:
                    f.write(response.read())
            return True
        except (URLError, HTTPError) as e:
            print(f"Download failed: {e}", file=sys.stderr)
            if attempt < retry_count:
                print(f"Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
    return False


def verify_checksum(file_path: Path, expected_sha256: str) -> bool:
    """Verify SHA256 checksum of downloaded file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    actual = sha256.hexdigest()
    if actual != expected_sha256:
        print(f"Error: Checksum mismatch", file=sys.stderr)
        print(f"  Expected: {expected_sha256}", file=sys.stderr)
        print(f"  Got: {actual}", file=sys.stderr)
        return False
    print("✓ Checksum verified")
    return True


def download_rmc(url: str, dest_dir: str, sha256: Optional[str] = None, tag: Optional[str] = None) -> int:
    """
    Download RMC jar from GitHub releases.
    
    Returns:
        0: Success
        1: Checksum mismatch
        2: Download failed
    """
    dest_path = Path(dest_dir)
    dest_path.mkdir(parents=True, exist_ok=True)
    jar_path = dest_path / "rmc.jar"
    
    # Check if valid jar already exists
    if is_valid_jar(jar_path):
        print(f"✓ Valid rmc.jar already exists at {jar_path}")
        return 0
    
    # Resolve URL based on input
    if "/releases/latest" in url:
        latest_tag = resolve_latest_release(url)
        if not latest_tag:
            print("Error: Could not resolve latest release", file=sys.stderr)
            return 2
        jar_name = f"rmc-{latest_tag}.jar"
        download_url = f"https://github.com/rebeca-lang/org.rebecalang.rmc/releases/download/{latest_tag}/{jar_name}"
    elif tag:
        jar_name = f"rmc-{tag}.jar"
        download_url = f"https://github.com/rebeca-lang/org.rebecalang.rmc/releases/download/{tag}/{jar_name}"
    else:
        download_url = url
    
    # Download with retry
    if not download_file(download_url, jar_path):
        print("Error: Failed to download RMC after retries", file=sys.stderr)
        return 2
    
    # Verify checksum if provided
    if sha256:
        if not verify_checksum(jar_path, sha256):
            return 1
    else:
        print("⚠ Warning: No checksum provided; downloaded jar not verified")
    
    print(f"✓ RMC downloaded to {jar_path}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Download RMC from GitHub releases")
    parser.add_argument("--url", required=True, help="GitHub release URL")
    parser.add_argument("--dest-dir", required=True, help="Destination directory")
    parser.add_argument("--sha256", help="Expected SHA256 checksum")
    parser.add_argument("--tag", help="Specific release tag")
    
    args = parser.parse_args()
    sys.exit(download_rmc(args.url, args.dest_dir, args.sha256, args.tag))


if __name__ == "__main__":
    main()
