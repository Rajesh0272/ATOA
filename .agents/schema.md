# Coordination Schema

Append one compact JSON object per line to `.agents/session-log.jsonl`.

Rules:

- Append only. Never edit or reorder old lines.
- One event per line. No pretty-printed JSON.
- Keep each line under 4 KB.
- Use repo-relative paths or globs in `scope`.
- Claims are advisory, not locks.

Common fields:

| Field | Required | Meaning |
| --- | ---: | --- |
| `ts` | yes | ISO-8601 UTC timestamp |
| `session` | yes | Unique session id, e.g. `codex-docs-20260905-a` |
| `agent` | yes | Person, agent, or role doing the work |
| `event` | yes | `claim`, `release`, `handoff`, `change`, `finding`, `decision`, `blocked` |
| `scope` | usually | Repo-relative path or glob |
| `note` | usually | Human-readable summary |
| `claim_id` | claim/release | Stable id minted by claimant |
| `ttl_min` | claim | Minutes before unreleased claim is stale |
| `to_agent` | handoff/blocked | Intended owner, or `all` |
| `validation` | change | Command/result summary |

Examples:

```json
{"ts":"2026-09-05T12:00:00Z","session":"codex-docs-20260905-a","agent":"codex","event":"claim","claim_id":"codex-docs-readme-001","scope":"README.md; DEMO_GUIDE.md","note":"polish setup and demo docs","ttl_min":60}
{"ts":"2026-09-05T12:20:00Z","session":"codex-docs-20260905-a","agent":"codex","event":"change","scope":"README.md; DEMO_GUIDE.md","note":"clarified quick start and demo flow","validation":"python -m pytest tests -q: pass"}
{"ts":"2026-09-05T12:21:00Z","session":"codex-docs-20260905-a","agent":"codex","event":"release","claim_id":"codex-docs-readme-001","scope":"README.md; DEMO_GUIDE.md","note":"done"}
```

Active non-stale claims:

```bash
jq -s 'map(select(.event=="claim" or .event=="release")) as $events | $events[] | select(.event=="claim") | . as $c | select(([ $events[] | select(.event=="release" and .claim_id==$c.claim_id) ] | length) == 0) | select(((now - (.ts|fromdateiso8601)) / 60) < (.ttl_min // 60)) | [.ts,.agent,.session,.claim_id,.scope,.note] | @tsv' .agents/session-log.jsonl
```

Open handoffs:

```bash
jq -r 'select(.event=="handoff" or .event=="blocked") | [.ts,.agent,((.to_agent // "all")),.scope,.note] | @tsv' .agents/session-log.jsonl
```
