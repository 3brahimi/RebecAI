# Verification & Scoring Contract

This document defines the 100-point rubric used by `score_single_rule.py` to evaluate Legata→Rebeca transformations.

## Scoring Rubric Definition

| Dimension | Points | Description | Verification Method |
| :--- | :--- | :--- | :--- |
| **Syntax** | 10 | Model and property parse without RMC errors | `rmc.jar` exit code |
| **Semantic Alignment**| 55 | Fidelity of mapping from Legata/COLREG to Rebeca | Currently placeholder; assumes validity on RMC pass |
| **Verification** | 25 | Successful property check by RMC | `rmc.jar` execution |
| **Integrity (Non-Hallucination)** | 10 | Absence of fabricated actors/variables | Symbol-diffing against source Legata rules |

**Total Maximum:** 100 points.

## Implementation Details

The `RubricScorer` operates as a state-based evaluator:

- **Pass**: 100 points (All criteria met).
- **Fail/Timeout**: 40 points (Syntax assumed correct, but model/property mapping failed).

## Future Directions: Semantic Validation & Mutation

### 1. Hallucination Detection (Identifier-Diffing)
To move away from binary scoring, we implement a **Symbol-Diffing** approach:
- **Extraction**: Parse the source Legata rule to define a "Golden Symbol Set".
- **Verification**: Extract identifiers (state variables/actors) from the generated `.rebeca`.
- **Classification**: 
    - **Syntax Error**: Caught by RMC compiler (exit code 5).
    - **Hallucination**: Identifiers found in the Rebeca model that are absent from the Golden Symbol Set (and not part of the Rebeca system library).

### 2. Mutation Strategies (Semantic Testing)
We will validate semantic strength by applying controlled mutations and verifying if the verification results change (Mutation Score).

| Artifact | Mutation Strategy | Impact |
| :--- | :--- | :--- |
| **.rebeca** | Transition Bypass | Ensure property fails if logic is skipped. |
| **.rebeca** | Predicate Flip | Ensure logic sensitivity (e.g., `>` → `<=`). |
| **.property**| Negation | Ensure `!A` fails if `A` passed. |
| **.property**| Logical Swap | Ensure logical operators (`&&`/`||`) are necessary. |

#### Model Mutations (`.rebeca`)
*   **Transition Bypass**: Forcibly bypass a `msgsrv` logic block.
    ```rebeca
    // Original:
    msgsrv updateLight(boolean on) { masthead_light_on = on; }
    // Mutation:
    msgsrv updateLight(boolean on) { /* masthead_light_on = on; */ }
    ```
*   **Predicate Flip**: Negate an `if` condition using the `!` operator.
    ```rebeca
    // Original: if (x > 0) { ... }
    // Mutation: if (!(x > 0)) { ... }
    ```
*   **Assignment Mutation**: Increment a counter variable.
    ```rebeca
    // Original: v = v + 1;
    // Mutation: v = v + 2;
    ```

#### Specification Mutations (`.property`)
*   **Negation**: Negate an entire assertion.
    ```rebeca
    // Original: Assertion: A;
    // Mutation: Assertion: !A;
    ```
*   **Logical Conjunction/Disjunction Swap**: Exchange `&&` with `||`.
    ```rebeca
    // Original: A && B
    // Mutation: A || B
    ```
*   **Variable Swap**: Replace a state variable with another from the same actor.
    ```rebeca
    // Original: s1.length > 50
    // Mutation: s1.speed > 50
    ```

### 3. Vacuity Checks
To ensure properties aren't passing vacuously (e.g., due to an impossible precondition), we will perform a secondary check:
- Verify `Assertion` passes for the model.
- Verify that `Assertion` fails if we assert `!Precondition`.
- **Cost**: Low; adds a single secondary RMC pass.
