# AIVAR demo scenarios

1. Normal run: Planner -> Coverage -> Generator -> Executor -> Quality Report.
2. Healing demo: change the Login button text in demo_web/index.html to Sign In. The generated test still expects Login; the analyzer proposes Sign In, deterministic validation checks it, and the complete test is rerun.
3. Defect demo: S005 navigates to /error. The HTTP 500 is classified as an application defect and escalated rather than healed.

Judge narration: The LLM proposes a structured healing candidate; deterministic validation gates it; the full test is rerun. Genuine application errors are escalated.
