import os
import sys
from pathlib import Path
import pytest

# Add the project root and skills folder to PYTHONPATH
root_dir = Path(__file__).parent.resolve()
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "skills" / "rebeca_tooling" / "scripts"))

# Run tests
if __name__ == "__main__":
    sys.exit(pytest.main(["tests/"]))
