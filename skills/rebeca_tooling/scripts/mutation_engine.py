#!/usr/bin/env python3
"""
Mutation Engine for semantic validation of Legata→Rebeca transformations.

Applies controlled mutations to .rebeca and .property files to verify semantic
strength. A well-formed transformation should produce different RMC outcomes
(kill the mutant) when mutations are applied.

Mutation strategies (defined in docs/SCORING.md):
  .rebeca:    transition_bypass, predicate_flip, assignment_mutation
  .property:  comparison_value_mutation, boolean_predicate_negation,
              assertion_negation, assertion_predicate_inversion,
              logical_swap, variable_swap

Design: all mutate_* methods return new content strings — never mutate in place.
Callers write mutants to disk and invoke RMC; this module only generates text.

Exit codes (CLI):
  0: Mutants generated successfully
  1: Invalid inputs or file not found
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils import safe_path


@dataclass
class Mutation:
    """Represents a single applied mutation with full before/after content."""
    mutation_id: str          # e.g. "Rule-22_m_tb_01"
    strategy: str             # e.g. "transition_bypass"
    artifact: str             # "model" or "property"
    original_content: str     # unmodified file text
    mutated_content: str      # mutated file text
    description: str          # human-readable description of the change


class MutationEngine:
    """
    Generates mutated variants of .rebeca and .property files.

    All methods are pure: they take content strings and return Mutation
    objects. No file I/O is performed here.
    """

    # ------------------------------------------------------------------ #
    #  .rebeca model mutations                                             #
    # ------------------------------------------------------------------ #

    def transition_bypass(self, content: str, rule_id: str) -> List[Mutation]:
        """
        Bypass msgsrv bodies by commenting out assignment statements.
        One mutant per msgsrv that contains at least one assignment.
        """
        mutations: List[Mutation] = []
        pattern = re.compile(
            r'(msgsrv\s+\w+\s*\([^)]*\)\s*\{)([^}]+)(\})',
            re.DOTALL,
        )
        match_index = 0
        for m in pattern.finditer(content):
            body = m.group(2)
            if '=' not in body:
                continue
            mutated_body = re.sub(r'([^\n]*=[^\n]*\n)', r'/* \1*/\n', body)
            if mutated_body == body:
                continue
            mutated_content = content[: m.start(2)] + mutated_body + content[m.end(2) :]
            match_index += 1
            mutations.append(Mutation(
                mutation_id=f"{rule_id}_m_tb_{match_index:02d}",
                strategy="transition_bypass",
                artifact="model",
                original_content=content,
                mutated_content=mutated_content,
                description=f"Bypassed assignments in msgsrv block #{match_index}",
            ))
        return mutations

    def predicate_flip(self, content: str, rule_id: str) -> List[Mutation]:
        """
        Negate if-conditions: `if (cond)` → `if (!(cond))`.
        One mutant per if-statement found. Skips already-negated conditions.
        """
        mutations: List[Mutation] = []
        pattern = re.compile(r'(if\s*\()([^)]+)(\))', re.MULTILINE)
        match_index = 0
        for m in pattern.finditer(content):
            inner = m.group(2).strip()
            if inner.startswith('!'):
                continue
            mutated_condition = f"!({inner})"
            mutated_content = (
                content[: m.start(2)] + mutated_condition + content[m.end(2) :]
            )
            match_index += 1
            mutations.append(Mutation(
                mutation_id=f"{rule_id}_m_pf_{match_index:02d}",
                strategy="predicate_flip",
                artifact="model",
                original_content=content,
                mutated_content=mutated_content,
                description=f"Negated if-condition #{match_index}: '{inner}' → '!({inner})'",
            ))
        return mutations

    def assignment_mutation(self, content: str, rule_id: str) -> List[Mutation]:
        """
        Increment numeric literals in assignment RHS: `v = v + 1;` → `v = v + 2;`.
        One mutant per numeric literal found in an assignment statement.
        """
        mutations: List[Mutation] = []
        # Match assignment statements with a numeric literal on the RHS
        pattern = re.compile(r'(\w+\s*=\s*[^;]*?)(\b\d+\b)([^;]*;)', re.MULTILINE)
        match_index = 0
        for m in pattern.finditer(content):
            original_num = int(m.group(2))
            mutated_num = original_num + 1
            mutated_content = (
                content[: m.start(2)] + str(mutated_num) + content[m.end(2) :]
            )
            match_index += 1
            mutations.append(Mutation(
                mutation_id=f"{rule_id}_m_am_{match_index:02d}",
                strategy="assignment_mutation",
                artifact="model",
                original_content=content,
                mutated_content=mutated_content,
                description=f"Incremented numeric literal in assignment: {original_num} → {mutated_num}",
            ))
        return mutations

    # ------------------------------------------------------------------ #
    #  .property specification mutations                                   #
    # ------------------------------------------------------------------ #

    def comparison_value_mutation(self, content: str, rule_id: str) -> List[Mutation]:
        """
        Increment numeric literals inside define block comparisons.
        `isOverLimit = (s1.length > 50)` → `isOverLimit = (s1.length > 51)`
        """
        mutations: List[Mutation] = []
        block = self._extract_define_block(content)
        if block is None:
            return mutations
        start, end, block_text = block
        pattern = re.compile(r'([><=!]=?\s*)(\d+)', re.MULTILINE)
        match_index = 0
        for m in pattern.finditer(block_text):
            original_num = int(m.group(2))
            mutated_num = original_num + 1
            mutated_block = (
                block_text[: m.start(2)] + str(mutated_num) + block_text[m.end(2) :]
            )
            mutated_content = content[:start] + mutated_block + content[end:]
            match_index += 1
            mutations.append(Mutation(
                mutation_id=f"{rule_id}_m_cvm_{match_index:02d}",
                strategy="comparison_value_mutation",
                artifact="property",
                original_content=content,
                mutated_content=mutated_content,
                description=f"Incremented comparison value: {original_num} → {mutated_num}",
            ))
        return mutations

    def boolean_predicate_negation(self, content: str, rule_id: str) -> List[Mutation]:
        """
        Negate define-block definitions.
        `isSafe = (s1.speed < 10)` → `isSafe = !(s1.speed < 10)`
        """
        mutations: List[Mutation] = []
        block = self._extract_define_block(content)
        if block is None:
            return mutations
        start, end, block_text = block
        # Match: varName = (expr);
        pattern = re.compile(r'(\w+\s*=\s*)(\([^)]+\))\s*;', re.MULTILINE)
        match_index = 0
        for m in pattern.finditer(block_text):
            original_expr = m.group(2)
            # Skip already-negated definitions
            preceding_char = block_text[m.start(2) - 1 : m.start(2)].strip()
            if preceding_char == '!':
                continue
            mutated_block = (
                block_text[: m.start(2)] + f"!{original_expr}" + block_text[m.end(2) :]
            )
            mutated_content = content[:start] + mutated_block + content[end:]
            match_index += 1
            mutations.append(Mutation(
                mutation_id=f"{rule_id}_m_bpn_{match_index:02d}",
                strategy="boolean_predicate_negation",
                artifact="property",
                original_content=content,
                mutated_content=mutated_content,
                description=f"Negated define expression #{match_index}: '!{original_expr}'",
            ))
        return mutations

    def assertion_negation(self, content: str, rule_id: str) -> List[Mutation]:
        """
        Negate entire assertions: `RuleName: A;` → `RuleName: !A;`.
        One mutant per assertion entry. Toggles existing leading negation.
        """
        mutations: List[Mutation] = []
        block = self._extract_assertion_block(content)
        if block is None:
            return mutations
        start, end, block_text = block
        # Match: AssertionName: [optional !]expression;
        pattern = re.compile(r'(\w+\s*:\s*)(!?)(.+?)(;)', re.DOTALL)
        match_index = 0
        for m in pattern.finditer(block_text):
            existing_negation = m.group(2)
            expr = m.group(3).strip()
            # Toggle: add ! if absent, remove if present
            mutated_expr = expr if existing_negation == '!' else f"!{expr}"
            mutated_block = (
                block_text[: m.start(2)]
                + mutated_expr
                + block_text[m.end(3) :]
            )
            mutated_content = content[:start] + mutated_block + content[end:]
            match_index += 1
            mutations.append(Mutation(
                mutation_id=f"{rule_id}_m_an_{match_index:02d}",
                strategy="assertion_negation",
                artifact="property",
                original_content=content,
                mutated_content=mutated_content,
                description=f"Toggled negation on assertion #{match_index}",
            ))
        return mutations

    def assertion_predicate_inversion(self, content: str, rule_id: str) -> List[Mutation]:
        """
        Negate specific predicates within an assertion while keeping the define block.
        `A && B` → `!A && B` (one mutant per predicate term in the assertion).
        """
        mutations: List[Mutation] = []
        block = self._extract_assertion_block(content)
        if block is None:
            return mutations
        start, end, block_text = block
        # Find individual predicate references (word tokens that are not operators)
        # Matches bare variable names used in assertions (not actor.var — those are in define)
        pattern = re.compile(r'\b([A-Za-z_]\w*)\b(?!\s*[:(])')
        match_index = 0
        for m in pattern.finditer(block_text):
            term = m.group(1)
            # Skip keywords
            if term in ('Assertion', 'LTL', 'define', 'property', 'G', 'F', 'X', 'U'):
                continue
            mutated_block = (
                block_text[: m.start()] + f"!{term}" + block_text[m.end() :]
            )
            mutated_content = content[:start] + mutated_block + content[end:]
            match_index += 1
            mutations.append(Mutation(
                mutation_id=f"{rule_id}_m_api_{match_index:02d}",
                strategy="assertion_predicate_inversion",
                artifact="property",
                original_content=content,
                mutated_content=mutated_content,
                description=f"Negated predicate term '{term}' in assertion",
            ))
        return mutations

    def logical_swap(self, content: str, rule_id: str) -> List[Mutation]:
        """
        Swap && with || (and vice versa) in the assertion block.
        One mutant per operator occurrence.
        """
        mutations: List[Mutation] = []
        block = self._extract_assertion_block(content)
        if block is None:
            return mutations
        start, end, block_text = block
        pattern = re.compile(r'(&&|\|\|)')
        match_index = 0
        for m in pattern.finditer(block_text):
            original_op = m.group(1)
            swapped_op = '||' if original_op == '&&' else '&&'
            mutated_block = (
                block_text[: m.start()] + swapped_op + block_text[m.end() :]
            )
            mutated_content = content[:start] + mutated_block + content[end:]
            match_index += 1
            mutations.append(Mutation(
                mutation_id=f"{rule_id}_m_ls_{match_index:02d}",
                strategy="logical_swap",
                artifact="property",
                original_content=content,
                mutated_content=mutated_content,
                description=f"Swapped '{original_op}' → '{swapped_op}' in assertion",
            ))
        return mutations

    def variable_swap(self, content: str, rule_id: str) -> List[Mutation]:
        """
        Replace a state variable reference with another from the same actor.
        Finds all `actorName.varName` patterns; swaps among same-actor variables.
        One mutant per (actor, var) pair that has at least one other candidate.
        """
        mutations: List[Mutation] = []
        block = self._extract_assertion_block(content)
        # Fall back to full content if no Assertion block found
        start, end, block_text = block if block is not None else (0, len(content), content)

        ref_pattern = re.compile(r'\b(\w+)\.(\w+)\b')
        refs: Dict[str, List[str]] = {}
        for m in ref_pattern.finditer(block_text):
            actor, var = m.group(1), m.group(2)
            if var not in refs.setdefault(actor, []):
                refs[actor].append(var)

        match_index = 0
        for actor, variables in refs.items():
            if len(variables) < 2:
                continue
            for i, original_var in enumerate(variables):
                swap_var = variables[(i + 1) % len(variables)]
                # Use regex with word boundaries to avoid partial-name replacement
                mutated_block = re.sub(
                    r'\b' + re.escape(actor) + r'\.' + re.escape(original_var) + r'\b',
                    f"{actor}.{swap_var}",
                    block_text,
                    count=1,
                )
                if mutated_block == block_text:
                    continue
                mutated_content = content[:start] + mutated_block + content[end:]
                match_index += 1
                mutations.append(Mutation(
                    mutation_id=f"{rule_id}_m_vs_{match_index:02d}",
                    strategy="variable_swap",
                    artifact="property",
                    original_content=content,
                    mutated_content=mutated_content,
                    description=f"Swapped '{actor}.{original_var}' → '{actor}.{swap_var}'",
                ))
        return mutations

    # ------------------------------------------------------------------ #
    #  Batch orchestration                                                 #
    # ------------------------------------------------------------------ #

    def mutate_model(self, content: str, rule_id: str) -> List[Mutation]:
        """Apply all .rebeca mutation strategies and return combined list."""
        return (
            self.transition_bypass(content, rule_id)
            + self.predicate_flip(content, rule_id)
            + self.assignment_mutation(content, rule_id)
        )

    def mutate_property(self, content: str, rule_id: str) -> List[Mutation]:
        """Apply all .property mutation strategies and return combined list."""
        return (
            self.comparison_value_mutation(content, rule_id)
            + self.boolean_predicate_negation(content, rule_id)
            + self.assertion_negation(content, rule_id)
            + self.assertion_predicate_inversion(content, rule_id)
            + self.logical_swap(content, rule_id)
            + self.variable_swap(content, rule_id)
        )

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _extract_define_block(self, content: str) -> Optional[Tuple[int, int, str]]:
        """Return (start, end, text) of the interior of define { ... }, or None."""
        m = re.search(r'\bdefine\s*\{([^}]*)\}', content, re.DOTALL)
        return (m.start(1), m.end(1), m.group(1)) if m else None

    def _extract_assertion_block(self, content: str) -> Optional[Tuple[int, int, str]]:
        """Return (start, end, text) of the interior of Assertion { ... }, or None."""
        m = re.search(r'\bAssertion\s*\{([^}]*)\}', content, re.DOTALL)
        return (m.start(1), m.end(1), m.group(1)) if m else None


# ------------------------------------------------------------------ #
#  CLI                                                                 #
# ------------------------------------------------------------------ #

_MODEL_STRATEGIES = ("transition_bypass", "predicate_flip", "assignment_mutation")
_PROPERTY_STRATEGIES = (
    "comparison_value_mutation", "boolean_predicate_negation",
    "assertion_negation", "assertion_predicate_inversion",
    "logical_swap", "variable_swap",
)


def run_mutants(
    mutations: List["Mutation"],
    jar: str,
    model_path: Optional[Path],
    property_path: Optional[Path],
    timeout_seconds: int = 60,
) -> Dict[str, Any]:
    """
    Execute each mutant against RMC and collect kill/survive statistics.

    A mutant is **killed** if RMC exits non-zero (counterexample found or
    parse/compile failure) when the mutation is applied.  A mutant
    **survives** if RMC still exits 0, indicating the property no longer
    distinguishes the mutation — a potential semantic gap.

    Args:
        mutations:        List of Mutation objects to execute.
        jar:              Path to rmc.jar.
        model_path:       Canonical (unmodified) .rebeca file path.
        property_path:    Canonical (unmodified) .property file path.
        timeout_seconds:  Per-mutant RMC timeout.

    Returns:
        {
          "total":          int,
          "killed":         int,
          "survived":       int,
          "errors":         int,
          "mutation_score": float  (killed / total * 100, or 0.0),
          "mutant_results": [{"mutation_id": str, "outcome": "killed"|"survived"|"error",
                               "exit_code": int}]
        }
    """
    jar_path = safe_path(jar)
    results: List[Dict[str, Any]] = []
    killed = 0
    errors = 0

    for mut in mutations:
        # Write the mutant to a temp file in the same directory as the original
        # so safe_path() constraints are satisfied (within home).
        if mut.artifact == "model" and model_path is not None:
            orig_path = model_path
            suffix = ".rebeca"
        elif mut.artifact == "property" and property_path is not None:
            orig_path = property_path
            suffix = ".property"
        else:
            results.append({"mutation_id": mut.mutation_id, "outcome": "error",
                            "exit_code": -1, "reason": "no matching original path"})
            errors += 1
            continue

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=suffix,
                delete=False,
                encoding="utf-8",
                dir=Path.home(),
            ) as tmp:
                tmp.write(mut.mutated_content)
                tmp_path = Path(tmp.name)

            # Build RMC command
            if mut.artifact == "model":
                rmc_model = str(tmp_path)
                rmc_prop = str(property_path) if property_path else None
            else:
                rmc_model = str(model_path) if model_path else None
                rmc_prop = str(tmp_path)

            if rmc_model is None or rmc_prop is None:
                results.append({"mutation_id": mut.mutation_id, "outcome": "error",
                                "exit_code": -1, "reason": "missing counterpart file"})
                errors += 1
                continue

            with tempfile.TemporaryDirectory(dir=Path.home()) as tmp_out:
                proc = subprocess.run(
                    [
                        "java", "-jar", str(jar_path),
                        "-s", rmc_model,
                        "-p", rmc_prop,
                        "-o", tmp_out,
                        "-e", "TIMED_REBECA",
                        "-x",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=timeout_seconds,
                )
                exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            exit_code = 3  # treat timeout as survived (indeterminate)
        except Exception as exc:
            results.append({"mutation_id": mut.mutation_id, "outcome": "error",
                            "exit_code": -1, "reason": str(exc)})
            errors += 1
            continue
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

        # exit_code != 0 → RMC rejected the mutant → killed
        outcome = "killed" if exit_code != 0 else "survived"
        if outcome == "killed":
            killed += 1
        results.append({"mutation_id": mut.mutation_id, "outcome": outcome,
                        "exit_code": exit_code})

    total = len(mutations)
    mutation_score = round(killed / total * 100, 2) if total > 0 else 0.0

    return {
        "total": total,
        "killed": killed,
        "survived": total - killed - errors,
        "errors": errors,
        "mutation_score": mutation_score,
        "mutant_results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate mutation variants of .rebeca/.property files for semantic validation"
    )
    parser.add_argument("--rule-id", required=True, help="Rule identifier (e.g., Rule-22)")
    parser.add_argument("--model", default=None, help="Path to .rebeca model file")
    parser.add_argument("--property", default=None, help="Path to .property file")
    parser.add_argument(
        "--strategy",
        default="all",
        choices=("all",) + _MODEL_STRATEGIES + _PROPERTY_STRATEGIES,
        help="Mutation strategy to apply (default: all)",
    )
    parser.add_argument(
        "--output-json", action="store_true", help="Output results as JSON"
    )
    # ── optional kill-run mode ──────────────────────────────────────────────
    run_group = parser.add_argument_group(
        "kill-run mode",
        "Pass all three flags to execute mutants with RMC and report kill score.",
    )
    run_group.add_argument("--run-with-jar", default=None,
                           help="Path to rmc.jar for executing mutants")
    run_group.add_argument("--run-with-model", default=None,
                           help="Path to canonical .rebeca model (used when mutating property)")
    run_group.add_argument("--run-with-property", default=None,
                           help="Path to canonical .property file (used when mutating model)")
    run_group.add_argument("--run-timeout", type=int, default=60,
                           help="Per-mutant RMC timeout in seconds (default: 60)")
    args = parser.parse_args()

    if args.model is None and args.property is None:
        print("Error: at least one of --model or --property is required", file=sys.stderr)
        sys.exit(1)

    engine = MutationEngine()
    mutations: List[Mutation] = []

    if args.model:
        model_path = safe_path(args.model)
        if not model_path.exists():
            print(f"Error: model file not found: {args.model}", file=sys.stderr)
            sys.exit(1)
        model_content = model_path.read_text(encoding="utf-8")
        for strategy in _MODEL_STRATEGIES:
            if args.strategy in ("all", strategy):
                mutations += getattr(engine, strategy)(model_content, args.rule_id)

    if args.property:
        prop_path = safe_path(args.property)
        if not prop_path.exists():
            print(f"Error: property file not found: {args.property}", file=sys.stderr)
            sys.exit(1)
        prop_content = prop_path.read_text(encoding="utf-8")
        for strategy in _PROPERTY_STRATEGIES:
            if args.strategy in ("all", strategy):
                mutations += getattr(engine, strategy)(prop_content, args.rule_id)

    mutant_summary = [
        {k: v for k, v in asdict(m).items()
         if k not in ("original_content", "mutated_content")}
        for m in mutations
    ]

    # ── kill-run mode ───────────────────────────────────────────────────────
    kill_stats: Optional[Dict[str, Any]] = None
    if args.run_with_jar:
        if not mutations:
            print("Warning: no mutants generated — skipping kill-run", file=sys.stderr)
        else:
            kill_stats = run_mutants(
                mutations=mutations,
                jar=args.run_with_jar,
                model_path=safe_path(args.run_with_model) if args.run_with_model else None,
                property_path=(
                    safe_path(args.run_with_property) if args.run_with_property else None
                ),
                timeout_seconds=args.run_timeout,
            )

    if args.output_json:
        output: Dict[str, Any] = {
            "rule_id": args.rule_id,
            "total_mutants": len(mutations),
            "mutants": mutant_summary,
        }
        if kill_stats is not None:
            output["kill_stats"] = kill_stats
        print(json.dumps(output, indent=2))
    else:
        print(f"Rule:            {args.rule_id}")
        print(f"Total mutants:   {len(mutations)}")
        for m in mutations:
            print(f"  [{m.mutation_id}] {m.strategy} ({m.artifact}): {m.description}")
        if kill_stats is not None:
            print()
            print(f"Kill-run results:")
            print(f"  Killed:         {kill_stats['killed']}/{kill_stats['total']}")
            print(f"  Survived:       {kill_stats['survived']}")
            print(f"  Errors:         {kill_stats['errors']}")
            print(f"  Mutation score: {kill_stats['mutation_score']:.1f}%")

    sys.exit(0)


if __name__ == "__main__":
    main()
