import json

from app.llm.client import LLMClient
from app.models.schemas import *


class CoverageAgent:

    def __init__(self):
        self.llm = LLMClient()

    def evaluate(self, plan):

        print()
        print("=" * 70)
        print("[AIVAR - STEP 3] COVERAGE ANALYSIS")
        print("=" * 70)

        print("[COVERAGE INPUT]")
        print(f"Application URL : {plan.application_url}")
        print(f"Total scenarios : {len(plan.scenarios)}")

        print()
        print("[SCENARIOS BEING ANALYZED]")

        for scenario in plan.scenarios:
            print(
                f"    {scenario.id} | "
                f"{scenario.category} | "
                f"{scenario.name}"
            )

        # ---------------------------------------------------------
        # MOCK MODE
        # ---------------------------------------------------------

        if self.llm.provider == "mock":

            categories = {
                s.category
                for s in plan.scenarios
            }

            category_names = {
                "happy_path": "Happy paths",
                "negative": "Negative paths",
                "edge_case": "Edge cases",
                "error_state": "Error states"
            }

            gaps = [
                CoverageGap(
                    category=category,
                    missing_scenario=f"Add {category_names[category]}",
                    reason=(
                        f"No {category_names[category].lower()} "
                        "scenario is present."
                    ),
                    risk=(
                        "high"
                        if category in ("happy_path", "error_state")
                        else "medium"
                    )
                )
                for category in category_names
                if category not in categories
            ]

            score = min(
                1.0,
                len(categories) / 4
            )

            result = CoverageAnalysis(
                score=score,
                covered_areas=[
                    category_names[c]
                    for c in categories
                ],
                gaps=gaps,
                should_replan=score < 0.75,
                reasoning=(
                    "Coverage is checked across happy paths, "
                    "negative paths, edge cases and error states."
                )
            )

            print()
            print("[COVERAGE OUTPUT - MOCK]")
            print(result.model_dump_json(indent=2))

            print("=" * 70)

            return result

        # ---------------------------------------------------------
        # GEMINI MODE
        # ---------------------------------------------------------

        system_prompt = """
You are AIVAR's Coverage Analysis Agent.

Your job is to analyze an existing software test plan and determine
whether the planned scenarios provide sufficient coverage.

You MUST analyze:

1. Happy paths
2. Negative paths
3. Edge cases
4. Error states

Your response will be parsed directly by a Python Pydantic model.

Therefore you MUST follow the exact JSON structure below.

IMPORTANT:

The "score" field MUST be a decimal between 0 and 1.

Examples:

100% = 1.0
90%  = 0.90
75%  = 0.75
65%  = 0.65
50%  = 0.50

Do NOT return 65 for 65%.

The exact output structure is:

{
  "score": 0.65,

  "covered_areas": [
    "Happy paths",
    "Negative paths"
  ],

  "gaps": [
    {
      "category": "edge_case",
      "missing_scenario": "Description of missing scenario",
      "reason": "Why this scenario is missing or important",
      "risk": "high"
    }
  ],

  "should_replan": true,

  "reasoning": "Explanation of the coverage analysis."
}

Rules:

1. "score" MUST be between 0 and 1.
2. "covered_areas" MUST be a list of strings.
3. "gaps" MUST be a list of objects.
4. Every gap MUST contain:
   - category
   - missing_scenario
   - reason
   - risk
5. risk MUST be exactly one of:
   - high
   - medium
   - low
6. "should_replan" MUST be true when coverage is below the
   configured coverage threshold.
7. "reasoning" MUST explain the coverage decision.
8. Do NOT use alternative field names.
9. Do NOT return:
   - coverage_score
   - analysis_summary
   - missing_scenarios
   - uncovered_edge_cases
   - uncovered_error_states
   - recommendations

Return JSON only.
"""

        schema_hint = """
{
  "score": 0.65,
  "covered_areas": [
    "Happy paths",
    "Negative paths"
  ],
  "gaps": [
    {
      "category": "edge_case",
      "missing_scenario": "string",
      "reason": "string",
      "risk": "medium"
    }
  ],
  "should_replan": true,
  "reasoning": "string"
}
"""

        user_prompt = json.dumps(
            plan.model_dump(),
            indent=2
        )

        print()
        print("[ACTION] Sending test plan to Gemini for coverage analysis...")

        data = self.llm.json_call(
            system=system_prompt,
            user=user_prompt,
            schema_hint=schema_hint
        )

        print()
        print("[COVERAGE] Validating Gemini response...")

        result = CoverageAnalysis.model_validate(data)

        print()
        print("[COVERAGE OUTPUT - VALIDATED]")
        print(f"Coverage score : {result.score}")
        print(f"Coverage %     : {result.score * 100:.1f}%")
        print(f"Covered areas  : {result.covered_areas}")
        print(f"Number of gaps: {len(result.gaps)}")
        print(f"Should replan  : {result.should_replan}")
        print(f"Reasoning      : {result.reasoning}")

        print()
        print("[COVERAGE GAPS]")

        for gap in result.gaps:
            print(
                f"    category={gap.category} | "
                f"scenario={gap.missing_scenario} | "
                f"risk={gap.risk}"
            )

        print("=" * 70)

        return result