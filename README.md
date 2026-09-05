# AIVAR — Autonomous Test Orchestration Agent

AIVAR accepts a web application URL, explores the live UI, creates a grounded
test plan, checks coverage, generates Playwright tests, executes them, and
classifies failures for safe healing or escalation.

## Pipeline

`URL -> Explorer -> Planner -> Coverage -> Generator -> Selector validation -> Playwright execution -> Failure analysis -> Healing/Escalation -> Quality report`

The architecture is intentionally closed-loop: coverage gaps can trigger
bounded replanning, and a locator is only healed when the candidate is
supported by the live DOM and passes deterministic validation.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload --port 8000
```

The UI is available at `http://127.0.0.1:8000`. The demo target can be served
separately with:

```bash
python scripts/serve_demo.py
```

## Credentials and secrets

The target URL is the only required input. Credentials are optional request
data and are supplied at runtime through the UI or `POST /run`:

```json
{
  "url": "https://target.example",
  "credentials": {
    "username": "test-user",
    "password": "provided-at-runtime"
  }
}
```

Credentials are not sent to the LLM and are redacted from generator logs.
Scenarios that require authentication are reported as `BLOCKED` when
credentials are not supplied; AIVAR does not guess credentials or silently
claim that an authenticated flow passed.

Store LLM keys in an uncommitted `.env` or a deployment secret manager. Never
place real keys or target credentials in `.env.example`, source code, prompts,
or committed artifacts.

## Provider configuration

Set `LLM_PROVIDER=mock`, `sarvam`, or `gemini`. For Sarvam, configure
`SARVAM_API_KEY`, `SARVAM_MODEL`, `SARVAM_MAX_TOKENS`, and
`SARVAM_REASONING_EFFORT`. For Gemini, configure `GEMINI_API_KEY` and
`GEMINI_MODEL`.

## Demo expectations

The included static demo is only a validation fixture. A real target may have
different authentication controls, routes, and business flows. The planner
and generator must use the live observation and runtime credentials rather
than assumptions from the fixture.
