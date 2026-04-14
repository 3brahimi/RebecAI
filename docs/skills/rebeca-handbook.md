# rebeca-handbook Skill

Modeling best practices, syntax examples, and common pitfalls for writing correct Rebeca actor models.

## Purpose

This skill provides:
- **Syntax reference** - Complete Rebeca language syntax
- **Modeling patterns** - Actor design best practices
- **Property specification** - Temporal logic formulas
- **Common pitfalls** - Mistakes to avoid
- **Debugging tips** - How to fix parse and compilation errors

## When to Use

Use this skill when:
- Writing Rebeca models from scratch
- Debugging parse errors
- Unsure about syntax or semantics
- Need property specification examples
- Want to understand RMC error messages

## Key Concepts

### Actor Model
Rebeca uses the actor model:
- **Actors** - Autonomous concurrent entities
- **Messages** - Asynchronous communication
- **State** - Local variables per actor
- **Handlers** - Message processing logic

### Reactive Classes
Define actor types:
```rebeca
reactiveclass Ship(int id) {
    statevars {
        int speed;
        int heading;
    }
    
    Ship() {
        speed = 0;
        heading = 0;
    }
    
    msgsrv updateSpeed(int newSpeed) {
        speed = newSpeed;
    }
}
```

### Main Block
Instantiate actors:
```rebeca
main {
    Ship ship1(1):();
    Ship ship2(2):();
}
```

### Properties
Specify safety/liveness:
```property
property {
    define {
        collision = (ship1.distance < 10);
    }
    
    assertion: !collision;
}
```

## Modeling Do's and Don'ts

### Do's
- ✓ Define all variables before using them
- ✓ Use parentheses for clarity in complex expressions
- ✓ Keep assertion logic simple and verifiable
- ✓ Test with concrete actor instances first
- ✓ Use meaningful variable names matching the domain (`vessel_type`, `light_on`)
- ✓ Validate property file syntax independently
- ✓ Archive counterexamples for regression testing

### Don'ts
- ✗ DON'T use implication operators (`->`, `=>`) — they are not valid in Rebeca properties
- ✗ DON'T chain variable assignments (`x = (y = value)`)
- ✗ DON'T reference undefined variables in assertions
- ✗ DON'T mix temporal operators (`G`, `F`) in the `Assertion` section — use `LTL` for those
- ✗ DON'T assume operator precedence — use explicit parentheses
- ✗ DON'T create properties without testing the model first
- ✗ DON'T ignore RMC error messages — they indicate real issues

## Property-Writing Examples

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

### Bad: Uses Implication (Forbidden)
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

### Good: Well-Structured with LTL
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

## Legata-to-Assertion Mapping Pattern

When converting a Legata clause, apply the pattern `(!condition || !exclude || assure)`:

```
Legata condition:  OS.Length > meters(50)
Rebeca define:     ship1_longer_50m = (s1.ship_length > 50);
Assertion:         Rule22: !ship1_longer_50m || ship1_lights_ok;

Legata exclude:    OS.Length < meters(12)
Rebeca define:     isSmall = (s1.ship_length < 12);
Assertion:         Rule23: !isPowerDriven || isSmall || lightsOn;
```

## Common Pitfalls

1. **Missing semicolons** - Every statement needs `;`
2. **Undefined variables** - Declare in statevars
3. **Type mismatches** - Check int/boolean types
4. **Message timing** - Use `after(delay)` for timing
5. **Property syntax** - Use `!` for negation, `&&` for AND

### Pitfall Quick-Reference

| Issue | Symptom | Fix |
|-------|---------|-----|
| Chained assignment | Compile error: unexpected `=` | Separate into define sections |
| Undefined variable | RMC error: unknown variable | Add to define section |
| Missing parentheses | Unexpected operator precedence | Add `()` around complex expressions |
| Temporal in Assertion | Property parse error | Move to LTL section |
| Non-determinism explosion | RMC timeout | Reduce non-det choices, pin values |

## RMC Error Messages

### Parse Errors (Exit Code 5)
- Syntax errors in `.rebeca` or `.property`
- Missing semicolons, braces, or keywords
- Undefined variables or types

### Compilation Errors (Exit Code 4)
- C++ compilation failed
- Usually indicates RMC code generation issue
- Check model for complex expressions

### Verification Failures
- Counterexample found
- Property violated by model
- Not a syntax error - model is unsafe

## Related Skills

- **[legata-to-rebeca](legata-to-rebeca.md)** - Workflow guidance
- **[rebeca-tooling](rebeca-tooling.md)** - Python automation library

## Related Agents

- **[legata-to-rebeca](../agents/legata-to-rebeca.md)** - Uses this skill for modeling guidance

## External Resources

- [Rebeca Language Official Site](http://rebeca-lang.org/)
- [RMC GitHub Repository](https://github.com/rebeca-lang/org.rebecalang.rmc)
