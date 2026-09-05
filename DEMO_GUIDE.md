# Demo Guide

Use this guide when presenting ATOA locally.

## Setup

Terminal 1:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```bash
source .venv/bin/activate
python scripts/serve_demo.py
```

Open `http://127.0.0.1:8000` and run against:

```text
http://127.0.0.1:9100
```

## Scenario 1: Normal Run

Show the default pipeline:

```text
Planner -> Coverage -> Generator -> Executor -> Quality Report
```

Expected talking points:

- The target URL is the only required input.
- The explorer reads the live page before planning.
- The report separates passed, failed, blocked, healed, and escalated results.

## Scenario 2: Healing

Set `AIVAR_MOCK_LOGIN_RENAME_FAILURE=1`, then run the demo against the unchanged
fixture. Mock generation will intentionally look for a `Login` button while the
live page exposes `Sign In`.

Expected talking points:

- The generated test fails because the expected accessible name differs.
- Failure analysis proposes a replacement from the current DOM.
- Deterministic validation gates the healing candidate.
- The full test is rerun after healing, not merely patched in memory.

## Scenario 3: Application Defect

Use the application error scenario. The demo's error route returns HTTP 500.

Expected talking points:

- Genuine application failures should be escalated.
- The healer should not hide server errors by changing selectors.
- A failed product behavior is different from a stale test.

## Good Closing Line

ATOA does not claim every generated test is correct. It records what it planned,
what it generated, what it actually executed, and what remains untested.
