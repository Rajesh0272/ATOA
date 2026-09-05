# Agent Coordination

This repo uses lightweight append-only coordination so multiple teammates and
agents can work without overwriting each other.

Before work:

1. Read `.agents/schema.md`.
2. Read the matching workflow in `.agents/workflows/`.
3. Check recent claims in `.agents/session-log.jsonl`.
4. Append a `claim` before editing files.

During work:

- Keep `.agents/session-log.jsonl` append-only. Never rewrite old entries.
- Use repo-relative paths in `scope`.
- Claims are advisory, not locks.
- If another active claim owns the same scope, append a `handoff` or choose a
  different scope.
- Never commit secrets, target credentials, or live provider keys.

After work:

- Append `change` with validation when code or docs changed.
- Append `release` when the claimed scope is free.
- Append `handoff` when another teammate should continue.

Fast reads:

```bash
jq -r 'select(.event=="handoff" or .event=="blocked" or .event=="decision") | [.ts,.event,.agent,((.to_agent // "-")),((.scope // "-")),.note] | @tsv' .agents/session-log.jsonl
```

```bash
jq -s 'map(select(.event=="claim" or .event=="release")) as $events | $events[] | select(.event=="claim") | . as $c | select(([ $events[] | select(.event=="release" and .claim_id==$c.claim_id) ] | length) == 0) | select(((now - (.ts|fromdateiso8601)) / 60) < (.ttl_min // 60)) | [.ts,.agent,.session,.claim_id,.scope,.note] | @tsv' .agents/session-log.jsonl
```
