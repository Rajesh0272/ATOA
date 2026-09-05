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
- Prefer 4-6 high-value scenarios for a simple observation (few elements, no forms/tables/lists), but scale
  up to as many as ~16 scenarios when the observation is rich (forms, navigation, cart/CRUD, search/filter/
  sort, tables, session-related controls, uploads/downloads) - follow the SCENARIO TAXONOMY and FORM
  VALIDATION DETECTION rules below to size the plan. Never invent a scenario just to hit a count; only
  generate scenarios the observation actually supports.
- When more candidate scenarios are supported than you can include, keep all "high priority" scenarios
  first, then fill remaining slots with "medium", then "low".

============================================================
SCENARIO TAXONOMY (generate every row below that the observation supports)
============================================================

Treat each row as "if the observation shows evidence of X, generate scenario(s) for Y", mapped onto the
existing category ("happy_path" | "negative" | "edge_case" | "error_state") / priority ("high" | "medium" |
"low") schema. Skip any row with no supporting evidence rather than inventing it.

Authentication / login (if a login form/fields are observed):
- Valid login -> happy_path, high.
- Invalid password, invalid username, empty username, empty password -> negative, high.
- Locked/disabled account message (only if observed) -> error_state, medium.
- Spaces-only credentials, SQL-injection-like credential input -> edge_case, medium.

Navigation (if multiple nav links/menu items are observed):
- One scenario per major discovered destination (home/dashboard/products/profile/orders/settings) verifying
  the link navigates and the destination heading/content becomes visible -> happy_path, medium.
- Logout (if a logout control is observed) -> happy_path, high.
- Accessing a protected/authenticated page while logged out, if that distinction is observable -> negative,
  medium.

Forms (beyond the FORM VALIDATION DETECTION section below):
- One happy-path "submit a valid form" scenario per distinct observed form -> happy_path, high.

Cart / CRUD (if add/remove/quantity controls, or create/edit/delete controls, are observed):
- Add an item, remove an item, update quantity/empty the cart -> happy_path, high for add, medium for
  remove/update.
- Adding the same item multiple times (quantity aggregation) -> edge_case, medium.
- Create/read/update/delete a record, for non-commerce CRUD UIs -> happy_path, high (create/read),
  medium (update/delete).

Search / filter / sort (if a search box, filter control, or sortable list/table is observed):
- Valid search returning results -> happy_path, medium.
- Empty search, no-results search, special-character search -> edge_case, medium.
- Applying/resetting a filter -> happy_path/negative depending on expected outcome, medium.
- Sorting a list/table by an observed sortable column -> happy_path, medium.

Tables (if a data table is observed):
- Verify row count / expected row content -> happy_path, medium.
- Pagination, if pagination controls are observed -> happy_path, medium.
- Empty-table state, only if a query can plausibly produce zero rows -> edge_case, low.

Session & commonly-forgotten flows (only when directly supported by observed controls/text):
- Forgot-password link/flow, if observed -> happy_path, medium.
- Session persists after refresh (reload the page after being authenticated) -> happy_path, medium.
- Browser back button after logout does not restore the authenticated view -> negative, medium.
Do NOT invent session-expiration/timeout scenarios requiring real elapsed time; only include them if the
observation gives concrete evidence (e.g. a visible "session expired" message/control).

Uploads / downloads (only if a file input or download link/button is observed):
- Upload a valid file, upload an unsupported file type -> happy_path / negative, medium.
- Trigger a download and assert the action is initiated (e.g. link/button is enabled and clickable) ->
  happy_path, low.

API / application failure classification (only if the observation itself shows evidence of a failure, e.g.
an error page, HTTP status text, or empty/broken content already present):
- Reflect the observed failure as an error_state scenario documenting the expected classification
  (application defect vs. missing test data) in expected_outcome -> error_state, high.

Dynamic UI (only if observed, e.g. a modal, tab, accordion, or spinner/loading indicator already present in
the observation):
- Opening a modal/tab/accordion reveals the expected content -> happy_path, low.

Accessibility smoke checks (only using elements actually observed):
- An observed primary button/control has a non-empty accessible name/label -> happy_path, low.

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