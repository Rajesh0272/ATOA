import json
from app.llm.client import LLMClient
from app.models.schemas import *
class PlannerAgent:
    def __init__(self): self.llm=LLMClient()
    def plan(self, obs):
        print()
        print("=" * 70)
        print("[AIVAR - STEP 2] TEST PLANNER")
        print("=" * 70)

        print("[PLANNER INPUT]")
        print(f"Application URL : {obs.url}")
        print(f"Application title : {obs.title}")
        print(f"Elements available : {len(obs.elements)}")
        print(f"Links available : {len(obs.links)}")
        print(f"Forms available : {len(obs.forms)}")

        for element in obs.elements:
            print(
                f"    element -> "
                f"tag={element.tag}, "
                f"text='{element.text}', "
                f"role={element.role}, "
                f"name={element.name}, "
                f"label={element.label}"
            )

        if self.llm.provider == "mock":
            plan = TestPlan(
                application_url=obs.url,
                application_summary=(
                    f"Web app titled '{obs.title}' "
                    "with interactive controls."
                ),
                scenarios=[
                    TestScenario(
                        id="S001",
                        name="Valid login",
                        flow="Enter valid credentials and submit login",
                        category="happy_path",
                        priority="high",
                        expected_outcome="Dashboard is displayed"
                    ),
                    TestScenario(
                        id="S002",
                        name="Invalid password",
                        flow=(
                            "Enter valid username and invalid "
                            "password and submit"
                        ),
                        category="negative",
                        priority="high",
                        expected_outcome=(
                            "Authentication error is displayed"
                        )
                    ),
                    TestScenario(
                        id="S003",
                        name="Empty credentials",
                        flow="Submit login without credentials",
                        category="edge_case",
                        priority="medium",
                        expected_outcome=(
                            "Validation messages are displayed"
                        )
                    ),
                    TestScenario(
                        id="S004",
                        name="Logout",
                        flow="Login and then logout",
                        category="happy_path",
                        priority="medium",
                        expected_outcome=(
                            "User returns to login page"
                        )
                    ),
                    TestScenario(
                        id="S005",
                        name="Application error handling",
                        flow=(
                            "Trigger a server-side failure "
                            "and verify error state"
                        ),
                        category="error_state",
                        priority="high",
                        expected_outcome="Error is surfaced"
                    )
                ],
                assumptions=[
                    "The application exposes a login flow."
                ]
            )

            print("[PLANNER OUTPUT - MOCK]")
            print(plan.model_dump_json(indent=2))
            print("=" * 70)

            return plan

        system_prompt = """
You are AIVAR's Test Planning Agent.

Analyze the supplied live application observation and create a concise, grounded software test plan.

Coverage requirements:
- Include happy_path, negative, edge_case, and error_state scenarios when they are supported by the observation.
- Do not generate only happy-path scenarios.
- Prefer 4-6 high-value scenarios over many repetitive scenarios.

Grounding rules:
1. Use only functionality supported by the supplied application observation.
2. Do NOT invent pages, APIs, error messages, redirects, credentials, backend behavior, or UI elements that were not observed.
3. When expected behavior cannot be confirmed from observation, state the uncertainty in assumptions rather than presenting it as a fact.
4. Scenario flows must reference observed controls/elements where possible.

Output rules:
- Return ONLY one valid JSON object.
- Do not return Markdown, code fences, explanations, or reasoning.
- Use EXACTLY these top-level fields: application_url, application_summary, scenarios, assumptions.
- Each scenario MUST contain: id, name, flow, category, priority, expected_outcome.
- category MUST be one of: happy_path, negative, edge_case, error_state.
- priority MUST be one of: high, medium, low.
- Keep strings concise.

Required JSON shape:
{
  "application_url": "string",
  "application_summary": "string",
  "scenarios": [
    {
      "id": "S001",
      "name": "string",
      "flow": "string",
      "category": "happy_path",
      "priority": "high",
      "expected_outcome": "string"
    }
  ],
  "assumptions": ["string"]
}
"""

        user_prompt = json.dumps(
            obs.model_dump(),
            indent=2
        )

        schema_hint = """
    {
    "application_url": "string",
    "application_summary": "string",
    "scenarios": [
        {
        "id": "S001",
        "name": "string",
        "flow": "string",
        "category": "happy_path",
        "priority": "high",
        "expected_outcome": "string"
        }
    ],
    "assumptions": []
    }
    """

        data = self.llm.json_call(
            system=system_prompt,
            user=user_prompt,
            schema_hint=schema_hint
        )

        print()
        print("[PLANNER] Validating LLM response against TestPlan...")
        
        plan = TestPlan.model_validate(data)

        print("[PLANNER OUTPUT - VALIDATED]")
        print(plan.model_dump_json(indent=2))
        print("=" * 70)

        return plan