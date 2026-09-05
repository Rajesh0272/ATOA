# Handoff Workflow

Use when another teammate or agent should continue work.

Append a `handoff` entry to `.agents/session-log.jsonl` with:

- `to_agent`: intended recipient, or `all`
- `scope`: repo-relative files or feature area
- `note`: what changed, what remains, and the next concrete step

Example:

```json
{"ts":"2026-09-05T12:30:00Z","session":"codex-cli-20260905-a","agent":"codex","event":"handoff","to_agent":"all","scope":"app/orchestration/orchestrator.py","note":"CLI entrypoint needs report artifact paths printed after run completion."}
```
