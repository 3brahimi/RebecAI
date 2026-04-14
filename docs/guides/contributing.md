# Contributing Guide

How to extend RebecAI with new agents, skills, and tooling.

## Overview

Contributions are welcome in three areas:
1. **Agents** - New workflow orchestration agents
2. **Skills** - New knowledge and guidance skills
3. **Tooling** - New Python library modules

## Adding New Agents

### 1. Create Agent Definition

Create `agents/your-agent-name.md`:

```markdown
---
name: your-agent-name
description: Brief description of what the agent does
---

# Agent Instructions

Detailed instructions for the agent...

## Required Inputs

1. Input 1 description
2. Input 2 description

## Workflow

1. Step 1
2. Step 2
...
```

### 2. Document the Agent

Create `docs/agents/your-agent-name.md`:

```markdown
# your-agent-name Agent

Description, capabilities, usage examples, etc.
```

### 3. Update Main README

Add agent to the "Agents" section in `README.md`.

### 4. Add Tests

Create acceptance tests in `tests/` directory.

### 5. Submit Pull Request

Include:
- Agent definition
- Documentation
- Tests
- Usage examples

## Adding New Skills

### 1. Create Skill Directory

```bash
mkdir -p skills/your-skill-name
```

### 2. Create Skill Definition

Create `skills/your-skill-name/SKILL.md`:

```markdown
# Your Skill Name

Description of the skill...

## Purpose

What this skill provides...

## When to Use

When to use this skill...

## Content

Detailed knowledge, patterns, examples...
```

### 3. Document the Skill

Create `docs/skills/your-skill-name.md`:

```markdown
# your-skill-name Skill

Overview, usage, examples, etc.
```

### 4. Update Main README

Add skill to the "Skills" section in `README.md`.

### 5. Submit Pull Request

Include:
- Skill definition
- Documentation
- Usage examples

## Adding New Tooling

### 1. Create Module

Create `skills/rebeca-tooling/lib/your_module.py`:

```python
"""
Brief description of the module.
"""

import argparse
from pathlib import Path

def your_function(param1: str, param2: int) -> dict:
    """
    Function description.

    Args:
        param1: Description
        param2: Description

    Returns:
        Dictionary with results
    """
    # Implementation
    return {"success": True}

def main():
    """CLI interface."""
    parser = argparse.ArgumentParser(description="Module description")
    parser.add_argument("--param1", required=True, help="Param1 description")
    parser.add_argument("--param2", type=int, default=10, help="Param2 description")

    args = parser.parse_args()
    result = your_function(args.param1, args.param2)

    print(result)
    return 0 if result["success"] else 1

if __name__ == "__main__":
    exit(main())
```

### 2. Export from Package

Update `skills/rebeca-tooling/lib/__init__.py`:

```python
from .your_module import your_function

__all__ = [
    # ... existing exports
    "your_function",
]
```

### 3. Add Tests

Create unit tests in `tests/test_your_module.py`:

```python
import unittest
from skills.rebeca_tooling.lib.your_module import your_function

class TestYourModule(unittest.TestCase):
    def test_your_function(self):
        result = your_function("test", 42)
        self.assertTrue(result["success"])
```

### 4. Update Documentation

Add function to `docs/guides/api-reference.md`:

```markdown
### your_function

Description...

\`\`\`python
from lib import your_function

result = your_function(param1="value", param2=42)
\`\`\`
```

### 5. Update Skill Documentation

Update `skills/rebeca-tooling/SKILL.md` to document the new module.

### 6. Submit Pull Request

Include:
- Module implementation
- Tests
- Documentation updates
- Usage examples

## Code Style

### Python

- Follow PEP 8
- Use type hints
- Document functions with docstrings
- Use `pathlib.Path` for file paths
- Handle errors explicitly

**Example:**
```python
from pathlib import Path

def process_file(file_path: str, timeout: int = 120) -> dict:
    """
    Process a file with timeout.

    Args:
        file_path: Path to file
        timeout: Timeout in seconds

    Returns:
        Dictionary with processing results

    Raises:
        FileNotFoundError: If file doesn't exist
        TimeoutError: If processing exceeds timeout
    """
    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Implementation
    return {"success": True, "path": str(path)}
```

### Markdown

- Use ATX-style headers (`#`)
- Include code blocks with language tags
- Use tables for structured data
- Link to related documentation

## Testing

### Run All Tests

```bash
# Acceptance tests
bash tests/run_full_acceptance_tests.sh

# Functional tests
bash tests/run_functional_tests.sh

# Leakage scan
bash tests/leakage_scanner.sh
```

### Test Coverage

Aim for:
- 80%+ code coverage
- All public functions tested
- Edge cases covered
- Error handling validated

## Documentation

### Required Documentation

For new agents:
- Agent definition (`agents/your-agent.md`)
- Agent documentation (`docs/agents/your-agent.md`)
- Usage examples
- README update

For new skills:
- Skill definition (`skills/your-skill/SKILL.md`)
- Skill documentation (`docs/skills/your-skill.md`)
- Usage examples
- README update

For new tooling:
- Module docstrings
- API reference update (`docs/guides/api-reference.md`)
- Skill documentation update
- Usage examples

### Documentation Style

- Clear and concise
- Include examples
- Link to related docs
- Use consistent formatting

## Pull Request Process

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make changes**
   - Implement feature
   - Add tests
   - Update documentation
4. **Run tests**
   ```bash
   bash tests/run_full_acceptance_tests.sh
   ```
5. **Commit changes**
   ```bash
   git commit -m "Add your-feature-name"
   ```
6. **Push to fork**
   ```bash
   git push origin feature/your-feature-name
   ```
7. **Create pull request**
   - Describe changes
   - Reference issues
   - Include examples

## Review Process

Pull requests will be reviewed for:
- Code quality and style
- Test coverage
- Documentation completeness
- Backward compatibility
- Platform support (Windows/macOS/Linux)

## Questions?

Open an issue for:
- Feature requests
- Bug reports
- Documentation improvements
- General questions

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
