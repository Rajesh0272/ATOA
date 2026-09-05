import json

from app.llm.client import LLMClient
from app.models.schemas import FailureDiagnosis


class FailureAnalyzer:

    def __init__(self):
        self.llm = LLMClient()

    def diagnose(self, evidence):

        print()
        print("=" * 70)
        print("[AIVAR - STEP 6] FAILURE ANALYSIS")
        print("=" * 70)

        print("[FAILURE ANALYZER INPUT]")

        if isinstance(evidence, dict):

            print(
                json.dumps(
                    evidence,
                    indent=2,
                    default=str
                )
            )

        else:

            print(evidence)

        if isinstance(evidence, dict):
            error_text = str(evidence.get("error", "")).lower()
            if (
                "unsupported selector strategy" in error_text
                or "missing a target" in error_text
                or "has no selector strategy" in error_text
            ):
                diagnosis = FailureDiagnosis(
                    failure_type="UNKNOWN",
                    confidence=0.99,
                    analysis=(
                        "The generated test is invalid because a non-navigation "
                        "step has no supported locator target. This is a test "
                        "generation or execution defect, not an application error."
                    ),
                    expected_locator=None,
                    healing_candidate=None,
                    business_intent_preserved=False,
                    safe_to_heal=False,
                )
                print()
                print("[FAILURE DIAGNOSIS - GENERATED TEST ERROR]")
                print(diagnosis.model_dump_json(indent=2))
                print("=" * 70)
                return diagnosis
            if "strict mode violation" in error_text:
                diagnosis = FailureDiagnosis(
                    failure_type="UNKNOWN",
                    confidence=0.99,
                    analysis=(
                        "The generated locator matched multiple elements. "
                        "This is an ambiguous test locator, not evidence that "
                        "the application renamed a control."
                    ),
                    expected_locator=(evidence.get("failed_step") or {}).get("target"),
                    healing_candidate=None,
                    business_intent_preserved=False,
                    safe_to_heal=False,
                )
                print()
                print("[FAILURE DIAGNOSIS - AMBIGUOUS GENERATED LOCATOR]")
                print(diagnosis.model_dump_json(indent=2))
                print("=" * 70)
                return diagnosis

        # =========================================================
        # MOCK MODE
        # =========================================================

        if self.llm.provider == "mock":

            error_text = json.dumps(
                evidence,
                default=str
            ).lower()

            # -----------------------------------------------------
            # Locator changed
            # -----------------------------------------------------

            if (
                "sign in" in error_text
                and "login" in error_text
            ):

                diagnosis = FailureDiagnosis(
                    failure_type="LOCATOR_CHANGED",
                    confidence=0.98,
                    analysis=(
                        "The expected Login button is no longer "
                        "present and the application exposes a "
                        "Sign In button instead."
                    ),
                    expected_locator={
                        "role": "button",
                        "name": "Login",
                    },
                    healing_candidate={
                        "role": "button",
                        "name": "Sign In",
                    },
                    business_intent_preserved=True,
                    safe_to_heal=True,
                )

                print()
                print("[FAILURE DIAGNOSIS - MOCK]")
                print(diagnosis.model_dump_json(indent=2))

                print("=" * 70)

                return diagnosis

            # -----------------------------------------------------
            # Application error
            # -----------------------------------------------------

            if (
                "internal server error" in error_text
                or "500" in error_text
                or "application error" in error_text
            ):

                diagnosis = FailureDiagnosis(
                    failure_type="APPLICATION_ERROR",
                    confidence=0.99,
                    analysis=(
                        "The application appears to be in an "
                        "error state. This is an application defect "
                        "rather than a locator problem."
                    ),
                    expected_locator=None,
                    healing_candidate=None,
                    business_intent_preserved=False,
                    safe_to_heal=False,
                )

                print()
                print("[FAILURE DIAGNOSIS - MOCK]")
                print(diagnosis.model_dump_json(indent=2))

                print("=" * 70)

                return diagnosis

            # -----------------------------------------------------
            # Default
            # -----------------------------------------------------

            diagnosis = FailureDiagnosis(
                failure_type="UNKNOWN",
                confidence=0.40,
                analysis=(
                    "The available evidence is insufficient "
                    "to safely determine the failure type."
                ),
                expected_locator=None,
                healing_candidate=None,
                business_intent_preserved=False,
                safe_to_heal=False,
            )

            print()
            print("[FAILURE DIAGNOSIS - MOCK]")
            print(diagnosis.model_dump_json(indent=2))

            print("=" * 70)

            return diagnosis

        # =========================================================
        # LLM MODE
        # =========================================================

        system_prompt = """
You are AIVAR's Failure Analysis Agent.

Your job is to analyze Playwright test failure evidence and determine
why the test failed.

The evidence may contain:

- failed step
- error message
- screenshot information
- DOM information
- page text
- expected locator
- current page elements
- browser information

Your response will be consumed directly by a Python Pydantic model.

Therefore you MUST follow the exact JSON structure below.

============================================================
FAILURE TYPES
============================================================

You MUST choose exactly one:

LOCATOR_CHANGED
ELEMENT_MISSING
TIMEOUT
ASSERTION_FAILED
APPLICATION_ERROR
UNKNOWN

============================================================
LOCATOR_CHANGED
============================================================

Use LOCATOR_CHANGED only when the expected UI element appears to
have changed its locator or accessible name while the intended
business action still exists.

Example:

Expected:

{
  "role": "button",
  "name": "Login"
}

Observed:

{
  "role": "button",
  "name": "Sign In"
}

Possible healing candidate:

{
  "role": "button",
  "name": "Sign In"
}

============================================================
ELEMENT_MISSING
============================================================

Use ELEMENT_MISSING when the intended element cannot be found and
there is insufficient evidence that it was merely renamed.

Do NOT invent a healing candidate.

============================================================
TIMEOUT
============================================================

Use TIMEOUT when the element or page did not become available within
the expected time.

Do not automatically classify every timeout as a locator change.

============================================================
ASSERTION_FAILED
============================================================

Use ASSERTION_FAILED when the element/action succeeded but the
expected business result was not observed.

============================================================
APPLICATION_ERROR
============================================================

Use APPLICATION_ERROR when evidence indicates an application defect,
such as:

- HTTP 500
- Internal Server Error
- server exception
- application error page
- backend failure

Do NOT recommend locator healing for application errors.

============================================================
UNKNOWN
============================================================

Use UNKNOWN when the evidence is insufficient.

============================================================
HEALING SAFETY
============================================================

A healing candidate is safe ONLY when all of these are true:

1. failure_type is LOCATOR_CHANGED
2. confidence is at least 0.90
3. business_intent_preserved is true
4. the candidate is supported by observed application evidence
5. the candidate does not change the intended business action

If any condition is not satisfied:

safe_to_heal MUST be false.

Do NOT claim that a healing candidate is safe simply because it
looks plausible.

============================================================
LOCATOR RULES
============================================================

Prefer:

1. role + name
2. label
3. visible text
4. id
5. selector

Do not invent random CSS selectors.

The healing candidate must be grounded in the observed evidence.

============================================================
EXACT OUTPUT STRUCTURE
============================================================

Return ONLY JSON:

{
  "failure_type": "LOCATOR_CHANGED",
  "confidence": 0.98,
  "analysis": "The Login button was renamed to Sign In.",
  "expected_locator": {
    "role": "button",
    "name": "Login"
  },
  "healing_candidate": {
    "role": "button",
    "name": "Sign In"
  },
  "business_intent_preserved": true,
  "safe_to_heal": true
}

IMPORTANT:

- Return ONLY JSON.
- Do NOT return markdown.
- Do NOT return ```json.
- Do NOT add commentary.
- Use EXACTLY the field names above.
- confidence MUST be between 0 and 1.
- expected_locator may be null.
- healing_candidate may be null.
"""

        schema_hint = """
{
  "failure_type": "LOCATOR_CHANGED | ELEMENT_MISSING | TIMEOUT | ASSERTION_FAILED | APPLICATION_ERROR | UNKNOWN",
  "confidence": 0.95,
  "analysis": "string",
  "expected_locator": {
    "role": "string",
    "name": "string",
    "label": "string",
    "text": "string",
    "id": "string",
    "selector": "string"
  },
  "healing_candidate": {
    "role": "string",
    "name": "string",
    "label": "string",
    "text": "string",
    "id": "string",
    "selector": "string"
  },
  "business_intent_preserved": true,
  "safe_to_heal": true
}
"""

        user_prompt = json.dumps(
            evidence,
            indent=2,
            default=str
        )

        print()
        print(
            "[ACTION] Sending failure evidence "
            "to LLM for diagnosis..."
        )

        data = self.llm.json_call(
            system=system_prompt,
            user=user_prompt,
            schema_hint=schema_hint,
        )

        print()
        print("[FAILURE ANALYZER] Validating LLM response...")

        diagnosis = FailureDiagnosis.model_validate(data)

        print()
        print("[FAILURE DIAGNOSIS - VALIDATED]")

        print(
            f"Failure type             : "
            f"{diagnosis.failure_type}"
        )

        print(
            f"Confidence               : "
            f"{diagnosis.confidence}"
        )

        print(
            f"Business intent preserved: "
            f"{diagnosis.business_intent_preserved}"
        )

        print(
            f"Safe to heal             : "
            f"{diagnosis.safe_to_heal}"
        )

        print(
            f"Analysis                 : "
            f"{diagnosis.analysis}"
        )

        print(
            f"Expected locator        : "
            f"{diagnosis.expected_locator}"
        )

        print(
            f"Healing candidate       : "
            f"{diagnosis.healing_candidate}"
        )

        print("=" * 70)

        return diagnosis