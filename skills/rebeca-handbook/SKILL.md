---
name: rebeca-handbook
version: 1.0.0
description: Practical guidance for writing correct Rebeca models and properties
trigger_phrases:
  - "rebeca syntax"
  - "property writing"
  - "rebeca examples"
  - "rmc script"
---

# Rebeca Modeling Guidelines Skill

## Rebeca Do's

✓ DO define all variables before using them
✓ DO use parentheses for clarity in complex expressions
✓ DO keep assertion logic simple and verifiable
✓ DO test with concrete actor instances first
✓ DO use meaningful variable names matching domain (vessel_type, light_on)
✓ DO validate property files syntax independently
✓ DO archive counterexamples for regression testing

## Rebeca Don'ts

✗ DON'T use implication operators (→, =>)
✗ DON'T chain variable assignments
✗ DON'T reference undefined variables
✗ DON'T mix temporal operators in assertion section
✗ DON'T assume operator precedence - use explicit parentheses
✗ DON'T create properties without testing model first
✗ DON'T ignore RMC error messages - they indicate real issues

## Syntax Examples

### Good: Simple Assertion
```
property {
  define {
    hasLight = s1.masthead_light_on;
    lightRange = s1.masthead_light_range;
  }
  Assertion {
    Rule22: !hasLight || (lightRange >= 6);
  }
}
```

### Bad: Uses Implication
```
property {
  define {
    hasLight = s1.masthead_light_on;
  }
  Assertion {
    Rule22: hasLight -> s1.masthead_light_range >= 6;  // FORBIDDEN
  }
}
```

### Good: Multi-Actor Coverage
```
property {
  define {
    ship1_rules = (s1.length > 50) || (s1.type != PowerDriven);
    ship2_rules = (s2.length > 50) || (s2.type != PowerDriven);
  }
  Assertion {
    BothShips: ship1_rules && ship2_rules;
  }
}
```

## Property-Writing Examples

### Good: Well-Structured Property
```
property {
  define {
    smallVessel = (s1.vessel_length < 12);
    powerDriven = (s1.vessel_type == PowerDriven);
    lightsActive = (s1.masthead_light_on && s1.sidelight_on);
  }
  Assertion {
    Rule23: !powerDriven || smallVessel || lightsActive;
  }
  LTL {
    Liveness: G(powerDriven -> F(lightsActive));
  }
}
```

### Bad: Undefined Variable
```
property {
  define {
    smallVessel = (s1.vessel_length < 12);
  }
  Assertion {
    Rule23: !powerDriven || smallVessel || lightsActive;  // undefined: powerDriven, lightsActive
  }
}
```

## RMC Toolchain Usage

### Python Library (Cross-Platform)

The **rebeca-tooling** skill provides all RMC operations:

```python
import sys
from pathlib import Path

# Reference rebeca-tooling skill
tooling_skill = Path("~/.agents/skills/rebeca-tooling").expanduser()
sys.path.insert(0, str(tooling_skill))

from lib import download_rmc, run_rmc

# Download RMC latest release
download_rmc(
    url="https://github.com/rebeca-lang/org.rebecalang.rmc/releases/latest",
    dest_dir=".agents/rmc"
)

# Download specific version
download_rmc(
    url="https://github.com/rebeca-lang/org.rebecalang.rmc/releases",
    dest_dir=".agents/rmc",
    tag="2.14"
)

# Run verification
result = run_rmc(
    jar=".agents/rmc/rmc.jar",
    model="./models/SimulationModelCode.rebeca",
    property_file="./properties/rule_22.property",
    output_dir="./verification_output",
    timeout_seconds=120,
    jvm_opts=["-Xms256m", "-Xmx2g"]
)

# Check result
if result == 0:
    print("Verification complete")
elif result == 5:
    print("Parse error - check Rebeca syntax")
elif result == 4:
    print("C++ compilation failed")
elif result == 3:
    print("Timeout")
```

### Command-Line Interface

For manual usage, CLI wrappers are available:

```bash
# Download RMC
python3 ~/.agents/skills/rebeca-tooling/lib/download_rmc.py \
  --url https://github.com/rebeca-lang/org.rebecalang.rmc/releases/latest \
  --dest-dir .agents/rmc

# Run verification
python3 ~/.agents/skills/rebeca-tooling/lib/run_rmc.py \
  --jar .agents/rmc/rmc.jar \
  --model ./models/SimulationModelCode.rebeca \
  --property ./properties/rule_22.property \
  --output-dir ./verification_output \
  --timeout-seconds 120 \
  --jvm-opt "-Xms256m" \
  --jvm-opt "-Xmx2g"
```

See the **rebeca-tooling** skill documentation for complete API reference.

## Common Pitfalls and Recovery

| Issue | Symptom | Fix |
|-------|---------|-----|
| Chained assignment | Compile error: unexpected `=` | Separate into define sections |
| Undefined variable | RMC error: unknown variable | Add to define section |
| Missing parentheses | Unexpected operator precedence | Add `()` around complex expressions |
| Temporal in assertion | Property parse error | Move to LTL section |
| Non-determinism explosion | RMC timeout | Reduce non-det choices, pin values |
