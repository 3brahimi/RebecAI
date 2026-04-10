# Documentation Index

Complete documentation for claude-rebeca agents and skills.

## Quick Start

- **[Installation Guide](guides/installation.md)** - Setup instructions for all platforms
- **[Usage Guide](guides/usage.md)** - Workflow execution examples
- **[Troubleshooting](guides/troubleshooting.md)** - Common issues and fixes

## Agents

- **[legata-to-rebeca](agents/legata-to-rebeca.md)** - Transform Legata/COLREG rules to Rebeca models
  - Capabilities, workflow phases, scoring rubric
  - Usage examples and expected output

## Skills

- **[legata-to-rebeca](skills/legata-to-rebeca.md)** - Workflow guidance skill
  - 8-phase transformation process
  - Practical examples and best practices

- **[rebeca-handbook](skills/rebeca-handbook.md)** - Modeling best practices skill
  - Syntax reference and modeling patterns
  - Common pitfalls and debugging tips

- **[rebeca-tooling](skills/rebeca-tooling.md)** - Python library skill
  - 11 cross-platform modules
  - CLI and library usage

## Guides

### Getting Started
- **[Installation](guides/installation.md)** - Platform-specific setup
- **[Usage](guides/usage.md)** - Complete workflow examples
- **[Troubleshooting](guides/troubleshooting.md)** - Common issues

### Advanced
- **[Architecture](guides/architecture.md)** - System design and components
- **[API Reference](guides/api-reference.md)** - Python library reference
- **[Contributing](guides/contributing.md)** - How to extend the system

## Documentation Structure

```
docs/
├── README.md                           # This file
├── agents/                             # Per-agent documentation
│   └── legata-to-rebeca.md            # Legata→Rebeca agent
├── skills/                             # Per-skill documentation
│   ├── legata-to-rebeca.md            # Workflow guidance skill
│   ├── rebeca-handbook.md             # Modeling best practices skill
│   └── rebeca-tooling.md              # Python library skill
└── guides/                             # Installation, usage, architecture
    ├── installation.md                 # Setup instructions
    ├── usage.md                        # Workflow examples
    ├── troubleshooting.md              # Common issues and fixes
    ├── architecture.md                 # System design
    ├── api-reference.md                # Python library reference
    └── contributing.md                 # How to contribute
```

## Navigation Tips

### By Role

**New Users:**
1. Start with [Installation Guide](guides/installation.md)
2. Read [Usage Guide](guides/usage.md)
3. Try examples from [legata-to-rebeca agent](agents/legata-to-rebeca.md)

**Developers:**
1. Read [Architecture Guide](guides/architecture.md)
2. Review [API Reference](guides/api-reference.md)
3. Check [Contributing Guide](guides/contributing.md)

**Researchers:**
1. Review [legata-to-rebeca agent](agents/legata-to-rebeca.md) for workflow
2. Check [rebeca-handbook skill](skills/rebeca-handbook.md) for modeling
3. See [Architecture Guide](guides/architecture.md) for system design

### By Task

**Installing:**
- [Installation Guide](guides/installation.md)

**Transforming Rules:**
- [legata-to-rebeca agent](agents/legata-to-rebeca.md)
- [Usage Guide](guides/usage.md)

**Writing Models:**
- [rebeca-handbook skill](skills/rebeca-handbook.md)

**Using Python Library:**
- [rebeca-tooling skill](skills/rebeca-tooling.md)
- [API Reference](guides/api-reference.md)

**Troubleshooting:**
- [Troubleshooting Guide](guides/troubleshooting.md)

**Contributing:**
- [Contributing Guide](guides/contributing.md)

## External Resources

- [Rebeca Language Official Site](http://rebeca-lang.org/)
- [RMC GitHub Repository](https://github.com/rebeca-lang/org.rebecalang.rmc)
- [Claude Code Documentation](https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/code-with-agents.html)
