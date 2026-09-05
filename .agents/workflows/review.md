# Review Workflow

Use for reviewing code, docs, or teammate changes.

1. Read `.agents/schema.md`.
2. Check active claims and recent changes.
3. Inspect the diff or files under review.
4. Lead with findings ordered by severity.
5. Include exact file and line references.
6. Note validation gaps separately from defects.

Review output should distinguish:

- App defect: product behavior is wrong.
- Test defect: generated or hand-written test is wrong.
- Harness defect: orchestration, execution, reporting, or healing is wrong.
- Documentation defect: docs are stale, misleading, or missing a required caveat.
