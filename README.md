# aws.serverless.architecture

Event & API platform on AWS serverless — proposal, decisions, and the spikes that test it.

Four spikes (A catalog, B LocalStack buses, C the join, D Custom Event Bus on real AWS), all with `findings.md` written.

```
docs/architecture/        the proposal: decisions, ADRs, conventions, PII, data layer, contracts, testing, roadmap, prompts
.claude/commands/arch/    the prompts as Claude Code commands  (/arch:spike-a-catalog-source-of-truth …)
spikes/A-…                catalog + generator skeleton + checks + tests   (no AWS)
spikes/B-…                LocalStack: 3 buses, probes, DLQ, harness, 19 tests (reads A's generated output since C)
spikes/C-join/            A joined to B: scenario tests and plan snapshots
spikes/D-…                Custom Event Bus on a real AWS account (eu-west-1)
```

## Quick start

1. Docker running, `mise` installed, then `mise install && task doctor`. Env vars (LocalStack token, AWS profile for Spike D) are listed in `.env.example`.
2. Spike A (no AWS): `task a:all`.
3. Spike B (LocalStack): `task b:up && task b:apply && task b:test`. It applies Spike A's generated output, so run step 2 first.
4. Spike C (the join): `task c:all` re-applies B's env and runs the scenarios (needs the licensed LocalStack token).
5. Spike D (real AWS, eu-west-1): `aws sso login --profile admin`, then `task d:apply && task d:test`; `task d:destroy` when done.

## Outcome

Each spike's `findings.md` holds its recommendation (go / go-with-changes / stop) and the ADR or roadmap edits it evidenced.
