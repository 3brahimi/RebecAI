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

## Common Pitfalls

1. **Missing semicolons** - Every statement needs `;`
2. **Undefined variables** - Declare in statevars
3. **Type mismatches** - Check int/boolean types
4. **Message timing** - Use `after(delay)` for timing
5. **Property syntax** - Use `!` for negation, `&&` for AND

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
