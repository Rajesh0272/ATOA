import json
from typing import Any

from app.config import settings


class LLMClient:

    def __init__(self):

        self.provider = settings.LLM_PROVIDER
        self.client = None

        print()
        print("=" * 70)
        print("[AIVAR - LLM CLIENT INITIALIZATION]")
        print("=" * 70)

        print(f"[CONFIG] Provider: {self.provider}")

        # ---------------------------------------------------------
        # GEMINI
        # ---------------------------------------------------------

        if self.provider == "gemini":

            if not settings.GEMINI_API_KEY:
                raise ValueError(
                    "LLM_PROVIDER=gemini but GEMINI_API_KEY is empty"
                )

            from google import genai

            self.client = genai.Client(
                api_key=settings.GEMINI_API_KEY
            )

            print("[CONFIG] Gemini API key loaded: True")
            print(f"[CONFIG] Gemini model: {settings.GEMINI_MODEL}")

        # ---------------------------------------------------------
        # SARVAM
        # ---------------------------------------------------------

        elif self.provider == "sarvam":

            if not settings.SARVAM_API_KEY:
                raise ValueError(
                    "LLM_PROVIDER=sarvam but SARVAM_API_KEY is empty"
                )

            from sarvamai import SarvamAI

            self.client = SarvamAI(
                api_subscription_key=settings.SARVAM_API_KEY
            )

            print("[CONFIG] Sarvam API key loaded: True")
            print(f"[CONFIG] Sarvam model: {settings.SARVAM_MODEL}")

        # ---------------------------------------------------------
        # MOCK
        # ---------------------------------------------------------

        elif self.provider == "mock":

            print("[CONFIG] Mock provider enabled")

        else:

            raise ValueError(
                f"Unsupported LLM_PROVIDER: {self.provider}"
            )

        print("=" * 70)

    # =============================================================
    # JSON CALL
    # =============================================================

    def json_call(
        self,
        system: str,
        user: str,
        schema_hint: str = ""
    ) -> dict[str, Any]:

        print()
        print("=" * 70)
        print("[AIVAR - LLM CALL]")
        print("=" * 70)

        print(f"[LLM PROVIDER] {self.provider}")

        print()
        print("[LLM INPUT - SYSTEM]")
        print(system)

        print()
        print("[LLM INPUT - USER]")
        print(user)

        print()
        print("[LLM INPUT - EXPECTED SCHEMA]")
        print(schema_hint)

        if self.provider == "mock":

            raise NotImplementedError(
                "Mock mode is implemented inside each agent."
            )

        # ---------------------------------------------------------
        # COMMON PROMPT
        # ---------------------------------------------------------

        # Keep instructions and application data as separate messages.
        # This makes the intended output contract clearer to the model.
        user_prompt = f"""
EXPECTED OUTPUT STRUCTURE:
{schema_hint}

USER/APPLICATION DATA:
{user}
"""

        # =========================================================
        # GEMINI
        # =========================================================

        if self.provider == "gemini":

            print()
            print("[ACTION] Sending request to Gemini...")
            print(f"[ACTION] Model: {settings.GEMINI_MODEL}")

            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=f"{system}\n\n{user_prompt}",
                config={
                    "response_mime_type": "application/json"
                }
            )

            raw_text = response.text

        # =========================================================
        # SARVAM
        # =========================================================

        elif self.provider == "sarvam":

            print()
            print("[ACTION] Sending request to Sarvam...")
            print(f"[ACTION] Model: {settings.SARVAM_MODEL}")

            response = self.client.chat.completions(
                model=settings.SARVAM_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": system + "\n\nIMPORTANT: Return ONLY valid JSON. No markdown, no explanations, and no reasoning in the final answer."
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                # Sarvam-105B has thinking enabled by default. Reasoning tokens
                # consume the same completion budget as the JSON answer. For
                # structured AIVAR agent outputs, disable thinking and reserve
                # enough tokens for the actual JSON.
                reasoning_effort=(
                    None
                    if settings.SARVAM_REASONING_EFFORT.lower()
                    in {"none", "off", "disabled", ""}
                    else settings.SARVAM_REASONING_EFFORT
                ),
                temperature=0.2,
                top_p=1,
                max_tokens=settings.SARVAM_MAX_TOKENS,
            )

            choice = response.choices[0] if response.choices else None
            message = choice.message if choice else None
            raw_text = message.content if message else None
            finish_reason = choice.finish_reason if choice else None

            print(f"[SARVAM DEBUG - FINISH REASON] {finish_reason}")
            print(f"[SARVAM DEBUG - CONTENT PRESENT] {raw_text is not None}")

            if raw_text is None:
                # Do not allow json.loads(None) to become an opaque FastAPI 500.
                # Give the caller the actual LLM failure mode.
                if finish_reason == "length":
                    raise RuntimeError(
                        "Sarvam response was truncated before producing JSON "
                        f"(finish_reason=length, max_tokens={settings.SARVAM_MAX_TOKENS})."
                    )

                raise RuntimeError(
                    "Sarvam returned no message content "
                    f"(finish_reason={finish_reason!r})."
                )

        else:

            raise ValueError(
                f"Unsupported provider: {self.provider}"
            )

        # =========================================================
        # PARSE JSON
        # =========================================================

        print()
        print("[LLM OUTPUT - RAW]")
        print(raw_text)

        # Be slightly defensive in case a provider ignores the JSON response
        # format and wraps the object in a markdown fence.
        if isinstance(raw_text, str):
            raw_text = raw_text.strip()
            if raw_text.startswith("```json") and raw_text.endswith("```"):
                raw_text = raw_text[len("```json"): -len("```")].strip()
            elif raw_text.startswith("```") and raw_text.endswith("```"):
                raw_text = raw_text[3:-3].strip()

        try:
            data = json.loads(raw_text)

        except (json.JSONDecodeError, TypeError) as e:

            print()
            print("[ERROR] LLM returned invalid JSON")
            print(f"[ERROR] {e}")

            raise

        print()
        print("[LLM OUTPUT - PARSED JSON]")
        print(json.dumps(data, indent=2))

        print("=" * 70)

        return data