# legata_to_rebeca Skill

Step-by-step workflow guidance for transforming Legata formal specifications into verifiable Rebeca actor models.

## Purpose

This skill provides:
- **Workflow templates** - Prescribed 8-phase transformation process
- **Practical examples** - Real-world Legata→Rebeca transformations
- **Best practices** - Patterns for actor modeling and property specification
- **Common pitfalls** - Mistakes to avoid during transformation

## When to Use

Use this skill when:
- Transforming Legata rules to Rebeca models
- Following the prescribed workflow (WF-01 through WF-08)
- Need guidance on actor modeling patterns
- Unsure how to structure properties

## Workflow Phases

### WF-01: Triage Rule Status
Classify the Legata rule as:
- `formalized` - Complete and correct
- `incomplete` - Missing components
- `incorrect` - Syntax or semantic errors
- `not-formalized` - No Legata available
- `todo-placeholder` - Placeholder only

### WF-02: Transform Legata → Rebeca
Generate `.rebeca` model file with:
- Actor definitions (reactiveclass)
- State variables
- Message handlers (msgsrv)
- Timing constraints

### WF-03: Generate Property
Generate `.property` file with:
- Safety properties (assertion)
- Liveness properties (eventually)
- Temporal logic formulas

### WF-04: COLREG Fallback
If Legata is incomplete/incorrect:
- Map to COLREG text
- Generate provisional property
- Document assumptions

### WF-05: Run RMC Verification
Execute model checker:
- Parse `.rebeca` and `.property`
- Compile C++ source
- Run verification
- Capture result (pass/fail/timeout/error)

### WF-06: Score Transformation
Apply 100-point rubric:
- Syntax correctness (40 pts)
- Semantic alignment (30 pts)
- Verification outcome (30 pts)

### WF-07: Generate Per-Rule Report
Produce JSON scorecard with:
- Rule ID
- Status classification
- Verification result
- Score breakdown
- Timestamps

### WF-08: Generate Aggregate Report
Produce summary report with:
- Total rules processed
- Success/failure counts
- Average scores
- Detailed findings

## Example Transformation

See [Usage Guide](../guides/usage.md) for complete examples.

## Related Skills

- **[rebeca-handbook](rebeca-handbook.md)** - Modeling best practices
- **[rebeca-tooling](rebeca-tooling.md)** - Python automation library

## Related Agents

- **[legata_to_rebeca](../agents/legata_to_rebeca.md)** - Uses this skill for workflow guidance
