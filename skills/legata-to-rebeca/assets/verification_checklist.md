# Pre-Verification Checklist

Before running RMC, ensure:

- [ ] All conditions from Legata `condition` block captured as guards
- [ ] All excludes from Legata `exclude` block negated in assertion
- [ ] All assure expressions conjunctively present in assertion
- [ ] No implication operators (→, =>) used
- [ ] No chained variable definitions
- [ ] Variable names consistent across multiple rules
- [ ] Assertion logic evaluates correctly
- [ ] Property file syntax is valid
- [ ] Model file syntax is valid
- [ ] RMC jar exists and is valid
- [ ] Output directory is writable
- [ ] Timeout value is reasonable (>30 seconds)

## Property Syntax Validation

```bash
# Check for forbidden operators
grep -E "\-\>|=>" rule_N.property && echo "ERROR: Found forbidden operators"

# Check for undefined variables
diff <(grep "define" rule_N.property | cut -d= -f1) \
     <(grep -oE "[a-zA-Z_][a-zA-Z0-9_]*" rule_N.property | sort -u)
```
