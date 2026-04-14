# Verification & Scoring Contract

This document defines the 100-point rubric used by `score_single_rule.py` to evaluate Legata→Rebeca transformations.

## Scoring Rubric Definition

| Dimension | Points | Description | Verification Method |
| :--- | :--- | :--- | :--- |
| **Syntax** | 10 | Model and property parse without RMC errors | `rmc.jar` exit code |
| **Semantic Alignment**| 55 | Fidelity of mapping from Legata/COLREG to Rebeca | Currently placeholder; assumes validity on RMC pass |
| **Verification** | 25 | Successful property check by RMC | `rmc.jar` execution |
| **Integrity (Non-Hallucination)** | 10 | Absence of fabricated actors/variables | Currently placeholder; awarded on RMC pass |

**Total Maximum:** 100 points.

## Implementation Details

The `RubricScorer` class operates as a state-based evaluator rather than an analytical one:

- **Verification Logic**: The script accepts a `verify_status` (pass/fail/timeout/blocked) passed from the RMC execution pipeline.
- **Score Calculation**: Scores are assigned in buckets:
    - **Pass**: 100 points (All criteria met).
    - **Fail/Timeout**: 40 points (Syntax is assumed correct, but model/property mapping failed).
- **Placeholder Warnings**:
    - *Semantic Alignment* and *Integrity* are currently **not** autonomously verified. The agent assumes that if RMC verification passes, the semantics are sufficiently aligned and no hallucination occurred.

## Future Directions: Testing Semantic Alignment

To evolve the rubric from a status-based assignment to true semantic validation, we propose the following testing strategies:

1. **Assertion-Mapping Unit Tests**: 
   - Extract conditions from Legata source files using a parser.
   - Compare extracted conditions against generated Rebeca assertions using AST (Abstract Syntax Tree) comparison.
   - Detect if the mapping pattern `(!condition || !exclude || assure)` has been structurally respected.

2. **Semantic Property Mutation**:
   - Introduce "mutants" into the generated Rebeca properties (e.g., negate a clause).
   - Re-run RMC verification. 
   - If the property still passes (or fails in an unexpected way), the original mapping likely had insufficient semantic strength.

3. **Symbolic Trace Analysis**:
   - Compare counterexample traces from RMC against Legata safety requirements.
   - Ensure the variables mentioned in Legata requirements are explicitly present and used in the corresponding Rebeca model transitions.

4. **Hallucination Detection**:
   - Implement a cross-reference check: parse all identifiers (actors/variables) in the generated `.rebeca` file and verify them against the set of entities defined in the source Legata file.
   - Flag any entities in the Rebeca model not derived from the Legata rule or standard system library.
