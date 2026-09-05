# Implement Workflow

Use for code or documentation changes.

1. Read `.agents/schema.md`.
2. Check active claims.
3. If the same scope is actively claimed, append a `handoff` or pick another
   scope.
4. Append a `claim` with `claim_id`, `scope`, and `ttl_min`.
5. Run `git status --short`.
6. Inspect before editing.
7. Edit only the claimed scope.
8. Validate with the narrowest useful command.
9. Append `change` with touched files and validation.
10. Append `release`.

Default validation:

- Python logic: `python -m pytest tests -q`
- Docs-only: run a stale-reference search relevant to the edit.
- Live provider work: document required env vars and whether a live API call was
  actually made.

Do not run unscoped `python -m pytest -q` unless you intentionally want to run
`scripts/test_sarvam.py`, which requires `SARVAM_API_KEY`.
