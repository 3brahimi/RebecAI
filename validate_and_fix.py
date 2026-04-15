import py_compile
import subprocess
import sys
from pathlib import Path

def run_checks():
    scripts = list(Path("skills/rebeca_tooling/scripts/").glob("*.py"))
    
    # 1. Syntax check
    for s in scripts:
        try:
            py_compile.compile(str(s), doraise=True)
        except py_compile.PyCompileError as e:
            print(f"Syntax Error in {s}: {e}")
            return False
            
    # 2. Check for unused imports and basic issues with flake8
    # Ignoring specific style errors to focus on runtime-breaking issues
    res = subprocess.run(["flake8", "skills/rebeca_tooling/scripts/", "--select=F,E9"], capture_output=True, text=True)
    if res.returncode != 0:
        print("Linting errors found:")
        print(res.stdout)
        # We need to manually fix F401 (unused imports)
        return False
        
    return True

if __name__ == "__main__":
    if not run_checks():
        sys.exit(1)
