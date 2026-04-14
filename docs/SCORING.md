# Verification & Scoring Contract

This document defines the 100-point rubric used by `score_single_rule.py` to evaluate Legata→Rebeca transformations.

## Scoring Rubric Definition

| Dimension | Points | Description | Verification Method |
| :--- | :--- | :--- | :--- |
| **Syntax** | 10 | Model and property parse without RMC errors | `rmc.jar` exit code |
| **Semantic Alignment**| 55 | Fidelity of mapping (Mutation & Vacuity Score) | Mutation Score × 0.55 |
| **Verification** | 25 | Successful property check by RMC | `rmc.jar` execution |
| **Integrity (Non-Hallucination)** | 10 | Absence of fabricated actors/variables | Symbol-diffing against source Legata rules |

**Total Maximum:** 100 points.

## Implementation Details

The `RubricScorer` now performs a weighted calculation for **Semantic Alignment**:

- **Semantic Alignment (55 pts)**: Calculated dynamically:
  ```python
  # (Mutation Score is 0.0 to 1.0)
  Semantic_Alignment = (Mutation_Score * 0.50) + (Vacuity_Pass ? 5 : 0)
  ```
  - **Mutation Testing (50 pts)**: A higher mutation score indicates the property is robust against semantic errors.
  - **Vacuity Check (5 pts)**: An additional bonus awarded if the property passes the vacuity test (proving it is non-trivial).


## Future Directions: Semantic Validation & Mutation

### 1. Hallucination Detection (Identifier-Diffing)
To move away from binary scoring, we implement a two-tier **Symbol-Diffing** approach:

- **Tier 1: Unused State Hallucination**:
  - **Detection**: Extract the set of state variables defined in the `.rebeca` file *before* and *after* the agent change.
  - **Logic**: Any variable added in the `.rebeca` file that is not referenced in any `msgsrv` logic or `define` or `Assertion` blocks is flagged as a "Dead-Code Hallucination."

- **Tier 2: Property-Reference Hallucination**:
  - **Detection**: Identify predicates in the `.property` file that refer to state variables.
  - **Logic**: If an added predicate references a variable that does not exist in the model, RMC will throw a syntax/reference error (Exit Code 5). We distinguish this from "rudimentary" syntax errors by cross-referencing the variable set: if the variable is missing from the *model's* definition but present in the *property's* reference, it is classified as a "Reference Hallucination" rather than a syntax typo.


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
These mutations target both the `define` block and the `Assertion` block to ensure robust verification.

**Define Block Mutations:**
*   **Comparison Value Mutation**: Increment or decrement a numeric literal.
    ```rebeca
    // Original: define { isOverLimit = (s1.length > 50); }
    // Mutation: define { isOverLimit = (s1.length > 51); }
    ```
*   **Boolean Predicate Negation**: Negate a definition to test the inverse.
    ```rebeca
    // Original: define { isSafe = (s1.speed < 10); }
    // Mutation: define { isSafe = !(s1.speed < 10); }
    ```

**Assertion Block Mutations:**
*   **Negation**: Negate an entire assertion.
    ```rebeca
    // Original: Assertion: A;
    // Mutation: Assertion: !A;
    ```
*   **Assertion-Level Predicate Inversion**: Negate specific predicate instances within an assertion while keeping the definition as-is.
    ```rebeca
    // Original: Assertion: A && B;
    // Mutation: Assertion: !A && B; // (or A && !B)
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
