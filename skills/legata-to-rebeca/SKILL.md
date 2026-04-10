---
name: legata-to-rebeca
version: 1.0.0
description: Step-by-step guidance for transforming Legata clauses into verified Rebeca models
trigger_phrases:
  - "transform legata to rebeca"
  - "formalize maritime rule"
  - "verify colreg compliance"
---

# Legata Formalization Workflow Skill

## When to Use
Use this skill when you need to transform a COLREG maritime safety rule from Legata formal specification into a verifiable Rebeca model.

## Rebeca Constraints (Embedded)

### Property File Structure
```
property {
  define {
    // Boolean variables for guards and assertions
    Variable1 = (condition1 && condition2);
    Variable2 = (actor.state > threshold);
  }
  Assertion {
    // Propositional logic only, no temporal operators
    SafetyRule: !guardCondition || assertionExpression;
  }
  LTL {
    // Temporal logic formulas
    Liveness: G(F(property));
  }
}
```

### Allowed Operations
- Comparisons: `<`, `>`, `==`, `<=`, `>=`
- Conjunctions: `&&`
- Disjunctions: `||`
- Negations: `!`
- Bitwise XOR: `^`

### Forbidden Patterns
- Implication: `->`, `=>`
- Chained assignments: `x = (y = value)`
- Temporal operators in Assertion section
- Undefined variable references

## Procedural Guidance

1. **Parse Legata Clause**
   - Extract `condition` block
   - Extract `exclude` block (if present)
   - Extract `assure` block

2. **Map State Variables**
   - Identify vessel properties (length, type, equipment)
   - Convert to Rebeca actor state variables
   - Use naming convention: `vessel_property` or `actor_property`

3. **Construct Assertion**
   - Pattern: `(!condition || !exclude || assure1 && assure2)`
   - Define all variables in `define` section first
   - Verify no forbidden operators used

4. **Verify Syntax**
   - Property file must parse without errors
   - All variables must be defined before use
   - Parenthesize all complex expressions

5. **Run RMC Verification**
   - Execute model checker with timeout
   - Analyze counterexamples if violations found
   - Iterate until passing or explicitly blocked

## Transformation Pattern Examples

### Equipment Range (Rule 22)
```
Legata condition: OS.Length > meters(50)
Rebeca define: ship1_longer_50m = (s1.ship_length > 50);
Assertion: Rule22: !ship1_longer_50m || ship1_lights_ok;
```

### Exclude Blocks (Rule 23)
```
Legata exclude: OS.Length < meters(12)
Rebeca define: isSmall = (s1.ship_length < 12);
Assertion: Rule23: !isPowerDriven || isSmall || lightsOn;
```

## Output Structure

- Created `.rebeca` files with updated model
- Created `.property` files with assertions
- Verification logs showing RMC results
- Per-rule scoring (9-point rubric)
