#!/usr/bin/env python3
"""Execute RMC model checker with model and property files."""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


def run_rmc(
    jar: str,
    model: str,
    property_file: str,
    output_dir: str,
    timeout_seconds: int = 120,
    jvm_opts: Optional[List[str]] = None
) -> int:
    """
    Execute RMC model checker.
    
    Returns:
        0: Success (parse + compile)
        1: Invalid inputs
        3: Timeout
        4: C++ compilation failed
        5: Rebeca parse failed
    """
    jar_path = Path(jar)
    model_path = Path(model)
    property_path = Path(property_file)
    output_path = Path(output_dir)
    
    # Validate inputs
    if not jar_path.exists():
        print(f"Error: JAR not found: {jar}", file=sys.stderr)
        return 1
    if not model_path.exists():
        print(f"Error: Model not found: {model}", file=sys.stderr)
        return 1
    if not property_path.exists():
        print(f"Error: Property not found: {property_file}", file=sys.stderr)
        return 1
    
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Build Java command
    cmd = ["java"]
    if jvm_opts:
        cmd.extend(jvm_opts)
    cmd.extend([
        "-jar", str(jar_path),
        "-s", str(model_path),
        "-p", str(property_path),
        "-o", str(output_path),
        "-e", "TIMED_REBECA",
        "-x"
    ])
    
    print("Executing RMC...")
    print(f"Command: {' '.join(cmd)}")
    
    # Execute with timeout
    stdout_log = output_path / "rmc_stdout.log"
    stderr_log = output_path / "rmc_stderr.log"
    
    try:
        with open(stdout_log, 'w') as stdout_f, open(stderr_log, 'w') as stderr_f:
            result = subprocess.run(
                cmd,
                stdout=stdout_f,
                stderr=stderr_f,
                timeout=timeout_seconds,
                cwd=str(output_path)
            )
            if result.returncode != 0:
                print(f"RMC execution failed with exit code {result.returncode}", file=sys.stderr)
                return result.returncode
    except subprocess.TimeoutExpired:
        print(f"Error: RMC verification timed out after {timeout_seconds}s", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"Error executing RMC: {e}", file=sys.stderr)
        return 1
    
    # Phase 1: Check if RMC generated C++ files (parse succeeded)
    cpp_files = list(output_path.glob("*.cpp"))
    if not cpp_files:
        print("Error: RMC failed to generate C++ files (parse error)", file=sys.stderr)
        print(f"Check {stderr_log} for Rebeca syntax errors", file=sys.stderr)
        return 5
    
    print("✓ Phase 1: RMC generated C++ source files")
    
    # Phase 2: Compile the C++ files with g++
    print("Phase 2: Compiling C++ files with g++...")
    compile_stderr = output_path / "compile_stderr.log"
    executable = output_path / "model.out"
    
    try:
        with open(compile_stderr, 'w') as stderr_f:
            result = subprocess.run(
                ["g++"] + [str(f) for f in cpp_files] + ["-w", "-o", str(executable)],
                stderr=stderr_f,
                cwd=str(output_path)
            )
            if result.returncode != 0:
                print("Error: Phase 2 failed - C++ compilation error", file=sys.stderr)
                print(f"Check {compile_stderr} for compiler errors", file=sys.stderr)
                print("Ensure g++ is installed: g++ --version", file=sys.stderr)
                return 4
    except FileNotFoundError:
        print("Error: g++ compiler not found", file=sys.stderr)
        print("Install g++: Ubuntu/Debian: sudo apt install build-essential", file=sys.stderr)
        print("            macOS: xcode-select --install", file=sys.stderr)
        return 4
    except Exception as e:
        print(f"Error during compilation: {e}", file=sys.stderr)
        return 4
    
    if not executable.exists():
        print("Error: Compilation reported success but no executable found", file=sys.stderr)
        return 4
    
    print("✓ Phase 2: C++ compilation succeeded")
    print("✓ RMC workflow complete (parse + compile)")
    print(f"Output directory: {output_path}")
    print(f"Executable: {executable}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Execute RMC model checker")
    parser.add_argument("--jar", required=True, help="Path to rmc.jar")
    parser.add_argument("--model", required=True, help="Path to .rebeca model file")
    parser.add_argument("--property", required=True, help="Path to .property file")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--timeout-seconds", type=int, default=120, help="Timeout in seconds")
    parser.add_argument("--jvm-opt", action="append", dest="jvm_opts", help="JVM options")
    
    args = parser.parse_args()
    sys.exit(run_rmc(
        args.jar,
        args.model,
        args.property,
        args.output_dir,
        args.timeout_seconds,
        args.jvm_opts
    ))


if __name__ == "__main__":
    main()
