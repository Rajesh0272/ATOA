import json

from app.llm.client import LLMClient
from app.models.schemas import (
    GeneratedTest,
    GenerationResult,
    TestStep,
)


class GeneratorAgent:

    def __init__(self):
        self.llm = LLMClient()

    @staticmethod
    def _log_safe(result):
        payload = result.model_dump()
        for test in payload.get("tests", []):
            for step in test.get("steps", []):
                target = step.get("target") or {}
                field = str(target.get("name") or target.get("label") or "").lower()
                if step.get("action") == "fill" and field in {"username", "email", "password"}:
                    step["value"] = "[REDACTED]"
        return payload

    @staticmethod
    def _add_authentication_prerequisite(test, observation, credentials):
        if not credentials or not observation or not test.requires_credentials:
            return

        has_login_click = any(
            step.action == "click"
            and step.target
            and str(step.target.get("name") or "").lower() in {"login", "sign in", "signin"}
            for step in test.steps
        )
        has_credential_fill = sum(
            1
            for step in test.steps
            if step.action == "fill"
            and step.target
            and str(
                step.target.get("name")
                or step.target.get("label")
                or step.target.get("value")
                or ""
            ).lower() in {"username", "email", "password"}
        ) >= 2
        if has_login_click or has_credential_fill:
            return

        username = next(
            (element for element in observation.elements
             if element.tag == "input" and (element.name or "").lower() in {"username", "email"}),
            None,
        )
        password = next(
            (element for element in observation.elements
             if element.tag == "input" and (element.name or "").lower() == "password"),
            None,
        )
        login_button = next(
            (element for element in observation.elements
             if element.tag == "button"
             and element.text.strip().lower() in {"login", "sign in", "signin"}),
            None,
        )
        if not username or not password or not login_button:
            test.credentials_available = False
            return

        navigate_index = next(
            (index for index, step in enumerate(test.steps)
             if step.action == "navigate"),
            -1,
        )
        insert_at = navigate_index + 1 if navigate_index >= 0 else 0
        prerequisite = [
            {
                "action": "fill",
                "target": {"role": "textbox", "name": username.name},
                "value": credentials.username,
            },
            {
                "action": "fill",
                "target": {"role": "textbox", "name": password.name},
                "value": credentials.password,
            },
            {
                "action": "click",
                "target": {"role": "button", "name": login_button.text.strip()},
                "value": None,
            },
        ]
        test.steps[insert_at:insert_at] = [
            TestStep.model_validate(step) for step in prerequisite
        ]

    @staticmethod
    def _add_cart_prerequisite(test, observation):
        if not observation:
            return
        product_hints = {
            element.selector_hint
            for element in observation.elements
            if element.tag == "button"
            and element.text.strip().lower() == "add to cart"
            and element.selector_hint
        }
        checkout_index = next(
            (
                index for index, step in enumerate(test.steps)
                if step.action == "click"
                and str((step.target or {}).get("name") or "").strip().lower() == "proceed to checkout"
            ),
            None,
        )
        checkout_field_index = next(
            (
                index for index, step in enumerate(test.steps)
                if step.action == "fill"
                and str((step.target or {}).get("name") or "").strip().lower()
                in {"customer_name", "customer_email", "address"}
            ),
            None,
        )
        if checkout_index is None and checkout_field_index is None:
            return
        insertion_index = checkout_index if checkout_index is not None else checkout_field_index
        if any(
            step.action == "click"
            and (
                str((step.target or {}).get("name") or "").strip().lower() == "add to cart"
                or "add-to-cart" in str((step.target or {}).get("selector") or "")
                or str((step.target or {}).get("selector_hint") or "").strip() in product_hints
            )
            for step in test.steps[:insertion_index]
        ):
            if checkout_index is None:
                test.steps.insert(
                    insertion_index,
                    TestStep(action="click", target={"role": "button", "name": "Proceed to checkout"}),
                )
            return
        product = next(
            (
                element for element in observation.elements
                if element.tag == "button"
                and element.text.strip().lower() == "add to cart"
                and element.selector_hint
            ),
            None,
        )
        if not product:
            return
        test.steps[insertion_index:insertion_index] = [
            TestStep(
                action="click",
                target={"selector": f'button.add-to-cart[data-product-id="{product.selector_hint}"]'},
            ),
            TestStep(action="click", target={"role": "button", "name": "Proceed to checkout"}),
        ]

    @staticmethod
    def _normalize_observed_targets(test, observation):
        if not observation:
            return
        observed = {element.selector_hint: element for element in observation.elements if element.selector_hint}
        for step in test.steps:
            target = step.target or {}
            hint = target.get("selector_hint")
            if not hint or hint not in observed:
                continue
            element = observed[hint]
            if element.tag == "button" and element.text.strip().lower() == "add to cart":
                step.target = {"selector": f'button.add-to-cart[data-product-id="{hint}"]'}
            elif element.tag in {"input", "select", "textarea", "button"}:
                step.target = {"id": hint}

    @staticmethod
    def _normalize_checkout_order(test):
        checkout_click = next(
            (
                index for index, step in enumerate(test.steps)
                if step.action == "click"
                and str((step.target or {}).get("name") or "").strip().lower()
                == "proceed to checkout"
            ),
            None,
        )
        checkout_assertion = next(
            (
                index for index, step in enumerate(test.steps)
                if step.action in {"assert_visible", "assert_text"}
                and str((step.target or {}).get("name") or "").strip().lower()
                == "checkout"
            ),
            None,
        )
        if checkout_click is not None and checkout_assertion is not None and checkout_assertion < checkout_click:
            step = test.steps.pop(checkout_click)
            test.steps.insert(checkout_assertion, step)

    def generate(self, plan, observation=None, credentials=None):

        print()
        print("=" * 70)
        print("[AIVAR - STEP 4] TEST GENERATION")
        print("=" * 70)

        print("[GENERATOR INPUT]")
        print(f"Application URL : {plan.application_url}")
        print(f"Total scenarios : {len(plan.scenarios)}")

        print()
        print("[SCENARIOS TO GENERATE]")

        for scenario in plan.scenarios:
            print(
                f"    {scenario.id} | "
                f"{scenario.category} | "
                f"{scenario.priority} | "
                f"{scenario.name}"
            )

        # =========================================================
        # MOCK MODE
        # =========================================================

        if self.llm.provider == "mock":

            tests = []

            for scenario in plan.scenarios:

                # Demo login flow
                if "login" in scenario.name.lower():

                    tests.append(
                        GeneratedTest(
                            id=f"TC-{scenario.id}",
                            scenario_id=scenario.id,
                            name=scenario.name,
                            steps=[
                                {
                                    "action": "navigate",
                                    "target": None,
                                    "value": plan.application_url,
                                },
                                {
                                    "action": "fill",
                                    "target": {
                                        "role": "textbox",
                                        "name": "username",
                                    },
                                    "value": credentials.username if credentials else None,
                                },
                                {
                                    "action": "fill",
                                    "target": {
                                        "role": "textbox",
                                        "name": "password",
                                    },
                                    "value": credentials.password if credentials else None,
                                },
                                {
                                    "action": "click",
                                    "target": {
                                        "role": "button",
                                        "name": "Login",
                                    },
                                    "value": None,
                                },
                                {
                                    "action": "assert_visible",
                                    "target": {
                                        "role": "button",
                                        "name": "Logout",
                                    },
                                    "value": None,
                                },
                            ],
                            business_assertions=[
                                "Successful login should show the logout control."
                            ],
                            requires_credentials=True,
                            credentials_available=bool(
                                credentials
                                and credentials.username
                                and credentials.password
                            ),
                        )
                    )

                # Generic fallback
                else:
                    observed_heading = next(
                        (
                            element.text.strip()
                            for element in (observation.elements if observation else [])
                            if element.tag in {"h1", "h2", "h3"} and element.text.strip()
                        ),
                        None,
                    )
                    generic_steps = [
                        {
                            "action": "navigate",
                            "target": None,
                            "value": plan.application_url,
                        }
                    ]
                    assertions = []
                    if "logout" in scenario.name.lower():
                        generic_steps.extend(
                            [
                                {
                                    "action": "click",
                                    "target": {"role": "button", "name": "Logout"},
                                    "value": None,
                                },
                                {
                                    "action": "assert_visible",
                                    "target": {"role": "button", "name": "Login"},
                                    "value": None,
                                },
                            ]
                        )
                    elif observed_heading:
                        generic_steps.append(
                            {
                                "action": "assert_text",
                                "target": {"selector": "body"},
                                "value": observed_heading,
                            }
                        )
                        assertions = [f"Page displays observed heading: {observed_heading}"]
                    tests.append(
                        GeneratedTest(
                            id=f"TC-{scenario.id}",
                            scenario_id=scenario.id,
                            name=scenario.name,
                            steps=generic_steps,
                            business_assertions=assertions,
                        )
                    )

            for test in tests:
                needs_authenticated_state = any(
                    step.target
                    and (
                        str(step.target.get("name") or "").lower()
                        in {"logout", "dashboard"}
                        or str(step.target.get("text") or "").lower()
                        in {"logout", "dashboard"}
                        or str(step.target.get("label") or "").lower()
                        in {"logout", "dashboard"}
                    )
                    for step in test.steps
                    if step.action in {"click", "assert_visible", "assert_text"}
                ) or any(
                    term in test.name.lower()
                    for term in ("logout", "dashboard", "authenticated")
                )
                if needs_authenticated_state:
                    test.requires_credentials = True
                    test.credentials_available = bool(
                        credentials and credentials.username and credentials.password
                    )
                self._add_authentication_prerequisite(test, observation, credentials)
                self._add_cart_prerequisite(test, observation)
                self._normalize_observed_targets(test, observation)
                self._normalize_checkout_order(test)

            result = GenerationResult(tests=tests)

            print()
            print("[GENERATOR OUTPUT - MOCK]")
            print(json.dumps(self._log_safe(result), indent=2))

            print("=" * 70)

            return result

        # =========================================================
        # LLM MODE
        # =========================================================

        system_prompt = """
You are AIVAR's Test Generation Agent.

Your job is to convert a software test plan into executable browser
test cases.

The generated tests will be executed by a Python Playwright executor.

Therefore, the output MUST follow the exact JSON structure specified
below.

============================================================
ALLOWED TEST ACTIONS
============================================================

Each test step MUST use exactly one of these actions:

1. navigate
2. fill
3. select
4. click
5. check
6. uncheck
7. hover
8. press
9. assert_visible
10. assert_not_visible
11. assert_text
12. assert_url
13. assert_count
14. assert_checked
15. assert_enabled
16. assert_disabled

Prefer the simplest action that expresses the intended user behavior or
business assertion. Use check/uncheck for checkboxes, hover for exposing
hidden menus, press for keyboard interactions (e.g. "Enter"), assert_url
for verifying navigation/redirect outcomes, and assert_count/assert_checked/
assert_enabled/assert_disabled for state-based assertions when they express
the expected outcome more precisely than assert_visible/assert_text.

============================================================
STEP FORMAT
============================================================

Each step has this structure:

{
  "action": "click",
  "target": {
    "role": "button",
    "name": "Login"
  },
  "value": null
}

For fill:

{
  "action": "fill",
  "target": {
    "role": "textbox",
    "name": "username"
  },
  "value": "{{TEST_USERNAME}}"
}

For navigate:

{
  "action": "navigate",
  "target": null,
  "value": "http://example.com"
}

For select:

{
  "action": "select",
  "target": {
    "id": "category"
  },
  "value": "outdoor"
}

For assert_visible:

{
  "action": "assert_visible",
  "target": {
    "role": "button",
    "name": "Logout"
  },
  "value": null
}

For assert_text:

{
  "action": "assert_text",
  "target": {
    "role": "heading",
    "name": "Dashboard"
  },
  "value": "Dashboard"
}

For assert_not_visible:

{
  "action": "assert_not_visible",
  "target": {
    "role": "button",
    "name": "Logout"
  },
  "value": null
}

============================================================
LOCATOR RULES
============================================================

Prefer semantic locators.

Preferred target fields:

1. role + name
2. label
3. text
4. id
5. selector

Do NOT invent selectors when the application observation does not
provide enough information.

For example, do not invent:

"#random-button"

when no such selector was observed.

Use only information supported by the application observation
or test plan.

For repeated controls such as multiple "Add to cart" buttons, use the
observed selector_hint (for example a product id) with an id or selector
target. Do not emit an unscoped locator that matches multiple controls.

============================================================
TEST DESIGN RULES
============================================================

For every planned scenario:

1. Generate one executable test.
2. Start with navigation when required.
3. Use realistic values.
4. Include the actions necessary to execute the scenario.
5. Include business assertions whenever possible.
6. Do not add unrelated actions.
7. Do not invent application functionality.
8. Every non-navigation step MUST have a non-null target with a supported
   locator strategy. A null target is valid only for navigate.
9. Use the application observation as the source of truth for available
   controls and locator names. If a scenario cannot be executed from the
   observation, do not invent a target or behavior.
10. When a login scenario requires credentials, use the configured test
    credentials supplied in the user input. Do not substitute an email
    address or other guessed credential.
11. Every business_assertions entry MUST have a corresponding
    assert_visible, assert_not_visible, or assert_text step. Do not describe an assertion that
    cannot be executed from an observed target and value.

The test must represent the business intent of the scenario.

============================================================
EXACT OUTPUT STRUCTURE
============================================================

Return ONLY this JSON structure:

{
  "tests": [
    {
      "id": "TC-S001",
      "scenario_id": "S001",
      "name": "Valid login",
      "steps": [
        {
          "action": "navigate",
          "target": null,
          "value": "http://example.com"
        },
        {
          "action": "fill",
          "target": {
            "role": "textbox",
            "name": "username"
          },
          "value": "{{TEST_USERNAME}}"
        },
        {
          "action": "click",
          "target": {
            "role": "button",
            "name": "Login"
          },
          "value": null
        }
      ],
      "business_assertions": [
        "Dashboard should be displayed after successful login."
      ]
    }
  ]
}

IMPORTANT:

- Return ONLY JSON.
- Do NOT return markdown.
- Do NOT use ```json.
- Do NOT add commentary.
- Do NOT use "generated_tests".
- Do NOT use "test_cases".
- The root field MUST be "tests".
- Every test MUST contain:
  id
  scenario_id
  name
  steps
  business_assertions
"""

        schema_hint = """
{
  "tests": [
    {
      "id": "string",
      "scenario_id": "string",
      "name": "string",
      "steps": [
        {
          "action": "navigate | fill | select | click | check | uncheck | hover | press | assert_visible | assert_not_visible | assert_text | assert_url | assert_count | assert_checked | assert_enabled | assert_disabled",
          "target": {
            "role": "string",
            "name": "string",
            "label": "string",
            "text": "string",
            "id": "string",
            "selector": "string"
          },
          "value": "string"
        }
      ],
      "business_assertions": [
        "string"
      ]
    }
  ]
}
"""

        generation_input = {
            "test_plan": plan.model_dump(),
            "credential_availability": bool(
                credentials and credentials.username and credentials.password
            ),
        }
        if observation is not None:
            generation_input["application_observation"] = observation.model_dump()

        user_prompt = json.dumps(generation_input, indent=2)

        print()
        print("[ACTION] Sending test plan to LLM for test generation...")

        data = self.llm.json_call(
            system=system_prompt,
            user=user_prompt,
            schema_hint=schema_hint,
        )

        print()
        print("[GENERATOR] Validating LLM response...")

        result = GenerationResult.model_validate(data)
        for test in result.tests:
            if not any(step.action == "navigate" for step in test.steps):
                test.steps.insert(
                    0,
                    TestStep(
                        action="navigate",
                        target=None,
                        value=plan.application_url,
                    ),
                )
        credential_values = (
            credentials.username,
            credentials.password,
        ) if credentials else (None, None        )
        for test in result.tests:
            needs_credentials = any(
                step.action == "fill"
                and step.target
                and (
                    str(step.target.get("name") or "").lower()
                    in {"username", "email", "password"}
                    or str(
                        step.target.get("label")
                        or step.target.get("value")
                        or ""
                    ).lower()
                    in {"username", "email", "password"}
                )
                for step in test.steps
            )
            needs_authenticated_state = any(
                step.target
                and (
                    str(step.target.get("name") or "").lower() in {"logout", "dashboard"}
                    or str(step.target.get("text") or "").lower() in {"logout", "dashboard"}
                    or str(step.target.get("label") or "").lower() in {"logout", "dashboard"}
                )
                for step in test.steps
                if step.action in {"click", "assert_visible", "assert_not_visible", "assert_text"}
            ) or any(
                term in test.name.lower()
                for term in ("logout", "dashboard", "authenticated")
            )
            needs_credentials = needs_credentials or needs_authenticated_state
            test.requires_credentials = needs_credentials
            test.credentials_available = bool(
                not needs_credentials
                or (credential_values[0] and credential_values[1])
            )
            if test.credentials_available and needs_credentials:
                for step in test.steps:
                    field = str(
                        (step.target or {}).get("name")
                        or (step.target or {}).get("label")
                        or (step.target or {}).get("value")
                        or ""
                    ).lower()
                    if step.action == "fill" and field in {"username", "email"}:
                        step.value = credential_values[0]
                    elif step.action == "fill" and field == "password":
                        step.value = credential_values[1]
            self._add_authentication_prerequisite(test, observation, credentials)
            self._add_cart_prerequisite(test, observation)
            self._normalize_observed_targets(test, observation)

        print()
        print("[GENERATOR OUTPUT - VALIDATED]")
        print(f"Generated tests : {len(result.tests)}")

        for test in result.tests:

            print()
            print(
                f"    {test.id} | "
                f"{test.scenario_id} | "
                f"{test.name}"
            )

            print(
                f"    Steps: {len(test.steps)}"
            )

            for index, step in enumerate(test.steps):

                print(
                    f"        Step {index + 1}: "
                    f"{step.action} | "
                    f"target={step.target} | "
                    f"value={'[REDACTED]' if step.action == 'fill' else step.value}"
                )

            print(
                f"    Business assertions: "
                f"{len(test.business_assertions)}"
            )

        print("=" * 70)

        return result