import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock")

    # Gemini
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    # Sarvam
    SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
    SARVAM_MODEL = os.getenv("SARVAM_MODEL", "sarvam-105b")
    # Sarvam reasoning tokens count against max_tokens.
    # Keep these explicit so model defaults cannot unexpectedly truncate JSON.
    SARVAM_MAX_TOKENS = int(os.getenv("SARVAM_MAX_TOKENS", "4096"))
    SARVAM_REASONING_EFFORT = os.getenv("SARVAM_REASONING_EFFORT", "none")

    # AIVAR
    HEADLESS = os.getenv("AIVAR_HEADLESS", "false").lower() == "true"

    # Remote browser (CDP). Set this to a browser-as-a-service websocket
    # endpoint (e.g. from Browserless.io or Browserbase) to connect to an
    # already running Chromium instead of launching one locally. Useful on
    # hosts that can't install/persist Playwright's browser binaries at
    # runtime (e.g. Vercel's Python serverless functions). Leave empty to
    # launch Chromium locally as usual (e.g. inside a Docker container
    # that already has it installed).
    BROWSER_WS_ENDPOINT = os.getenv("BROWSER_WS_ENDPOINT", "")

    COVERAGE_THRESHOLD = float(os.getenv("COVERAGE_THRESHOLD", "0.75"))
    MAX_REPLAN_ATTEMPTS = int(os.getenv("MAX_REPLAN_ATTEMPTS", "2"))
    MAX_HEAL_ATTEMPTS = int(os.getenv("MAX_HEAL_ATTEMPTS", "1"))


settings = Settings()