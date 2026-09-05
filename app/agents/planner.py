import json
from app.llm.client import LLMClient
from app.models.schemas import *
class PlannerAgent:
    def __init__(self): self.llm=LLMClient()
    def plan(self, obs, prd_text=None, intent=None):
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
        if intent:
            print(f"Developer intent : {intent}")
        if prd_text:
            print(f"PRD supplied : {len(prd_text)} chars")

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
                ] + ([f"Developer intent considered: {intent}"] if intent else [])
                  + (["A PRD excerpt was supplied and used to scope priorities."] if prd_text else [])
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
- Prefer 4-6 high-value scenarios over many repetitive scenarios, unless the observation contains one or
  more forms, in which case follow the FORM VALIDATION DETECTION rules below to size the plan.

============================================================
FORM VALIDATION DETECTION (when the observation contains forms/inputs)
============================================================

When the observation includes form elements (inputs, selects, checkboxes, radios, textareas), inspect the
observed labels/names/roles/input-related text to infer which validation categories plausibly apply, and
generate one scenario per applicable, observed rule. Only generate a scenario for a category if the
observation gives evidence the field exists (e.g. a field labeled/named "email" supports email validation
scenarios; do not assume an email field exists otherwise). Map each detected rule onto the existing
category/priority schema as follows:

- Required field left empty (text/dropdown/checkbox/radio) -> category "negative", priority "high".
- Email format issues (missing "@", missing domain, multiple "@", stray whitespace, case handling) ->
  category "negative", priority "high" for missing/invalid format, "low" for case-handling checks.
- Password rules (too short, missing uppercase/lowercase/number/special character, weak-password warning) ->
  category "negative", priority "high".
- Confirm-password mismatch or empty confirmation -> category "negative", priority "high".
- Phone number issues (too few/many digits, letters, special characters, country code handling) ->
  category "negative", priority "medium".
- Numeric field issues (negative values, decimals where an integer is expected, alphabetic input) ->
  category "negative", priority "medium"; boundary/min-max values -> category "edge_case", priority "medium".
- Text field edge cases (special characters, SQL-injection-like input, XSS-like input, very long input,
  unicode/emoji input) -> category "edge_case", priority "medium" (raise to "high" only if the field is
  clearly security-sensitive, e.g. a login/search field).
- Date field issues (invalid format, end date before start date, past/future restrictions) ->
  category "negative" for invalid input, "edge_case" for boundary/range rules; priority "medium".
- Dropdown left at its default "Select..." placeholder value -> category "negative", priority "medium".
- Do not fabricate validation messages: phrase expected_outcome as the generic expected behavior (e.g.
  "A validation error is shown and the form is not submitted") unless the observation includes the exact
  message text.
- When a form is present, prefer covering distinct validation rules across its fields over repeating
  the same rule on multiple similar fields.

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

============================================================
DEVELOPER INTENT (optional)
============================================================

If a developer intent statement is supplied, prioritize scenarios that
reflect it (e.g. "focus on checkout and authentication flows" should bias
scenario selection toward those flows) while still respecting grounding
rules and never inventing unobserved functionality.

============================================================
PRODUCT REQUIREMENTS DOCUMENT (optional)
============================================================

If a PRD excerpt is supplied, use it only to prioritize and scope which
observed functionality to test. Do not create scenarios for PRD
requirements that have no supporting evidence in the application
observation; instead note the gap in assumptions.
"""

        context_prompt = ""
        if intent:
            context_prompt += f"\nDEVELOPER INTENT:\n{intent}\n"
        if prd_text:
            context_prompt += f"\nPRODUCT REQUIREMENTS DOCUMENT (excerpt):\n{prd_text[:6000]}\n"

        user_prompt = context_prompt + json.dumps(
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