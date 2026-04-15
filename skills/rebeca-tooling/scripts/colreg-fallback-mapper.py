#!/usr/bin/env python3
"""
Generate provisional Rebeca properties from COLREG source text when Legata is unusable.
Returns property with confidence and assumption tracking.
"""

import json
import sys
from typing import Dict, Any, List

class COLREGFallbackMapper:
    """Maps COLREG text to provisional Rebeca properties."""
    
    def map_rule(self, rule_id: str, colreg_text: str) -> Dict[str, Any]:
        """
        Generate provisional mapping from COLREG source text.
        
        Returns dict with:
            - provisional_property: Rebeca property placeholder
            - confidence: high|medium|low
            - assumptions: list of assumptions made
            - requires_manual_review: bool
            - mapping_path: "colreg-fallback"
        """
        
        result = {
            "rule_id": rule_id,
            "provisional_property": "",
            "confidence": "low",
            "assumptions": [],
            "requires_manual_review": True,
            "mapping_path": "colreg-fallback"
        }
        
        if not colreg_text or len(colreg_text.strip()) == 0:
            result["provisional_property"] = "property { Assertion { DefaultRule: true; } }"
            result["assumptions"].append("No COLREG source text provided")
            return result
        
        # Analyze COLREG text for common patterns
        assumptions = []
        actors = []
        conditions = []
        
        # Extract potential actors
        colreg_keywords = [
            "vessel", "ship", "boat", "aircraft",
            "light", "shape", "signal", "whistle",
            "visibility", "darkness", "fog"
        ]
        
        for keyword in colreg_keywords:
            if keyword.lower() in colreg_text.lower():
                if keyword not in actors:
                    actors.append(keyword)
        
        # Extract negation and conjunction/disjunction intent (for operator selection only)
        has_negation = "not" in colreg_text.lower() or "shall not" in colreg_text.lower()
        has_conjunction = "and" in colreg_text.lower()
        has_disjunction = "or" in colreg_text.lower()

        if has_negation:
            assumptions.append("Negation detected - obligation mapped to !guard || assure pattern")
        if has_conjunction:
            assumptions.append("Conjunction detected - multiple conditions ANDed")
        if has_disjunction:
            assumptions.append("Disjunction detected - alternative conditions ORed")

        # Build define entries from extracted actor keywords
        define_vars = []
        for actor in actors[:3]:
            var_name = f"{actor}_condition"
            define_vars.append((var_name, actor))

        # Build assertion expression from define vars
        if define_vars:
            var_names = [v for v, _ in define_vars]
            if has_negation:
                # Obligation pattern: !guard || assure
                assertion_expr = f"!{var_names[0]}"
                if len(var_names) > 1:
                    assertion_expr += " || " + " && ".join(var_names[1:])
            elif has_disjunction and len(var_names) > 1:
                assertion_expr = " || ".join(var_names)
            else:
                assertion_expr = " && ".join(var_names)
        else:
            assertion_expr = "true"

        # Build provisional property
        property_lines = [
            "property {",
            "  define {",
            "    // Provisional mapping from COLREG source text"
        ]

        for var_name, actor in define_vars:
            property_lines.append(f"    {var_name} = ({actor}.state > 0);")

        property_lines.extend([
            "  }",
            "  Assertion {",
            f"    COLREGRule: {assertion_expr};",
            "  }",
            "  LTL {",
            "    // Temporal properties from COLREG",
            "    G(COLREGRule);",
            "  }",
            "}"
        ])
        
        result["provisional_property"] = "\n".join(property_lines)
        result["assumptions"] = assumptions

        # Determine confidence based on evidence richness
        evidence_count = len(actors) + (1 if has_negation else 0) + (1 if has_conjunction or has_disjunction else 0)
        if evidence_count >= 3:
            result["confidence"] = "medium"
        else:
            result["confidence"] = "low"
        
        return result


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Map COLREG text to provisional Rebeca property")
    parser.add_argument("--rule-id", required=True, help="Rule identifier")
    parser.add_argument("--colreg-text", required=True, help="COLREG rule text")
    parser.add_argument("--output-json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    mapper = COLREGFallbackMapper()
    result = mapper.map_rule(args.rule_id, args.colreg_text)
    
    if args.output_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Rule: {result['rule_id']}")
        print(f"Confidence: {result['confidence']}")
        print(f"Requires Review: {result['requires_manual_review']}")
        print(f"\nAssumptions:")
        for assumption in result['assumptions']:
            print(f"  - {assumption}")
        print(f"\nProvisional Property:")
        print(result['provisional_property'])


if __name__ == "__main__":
    main()
