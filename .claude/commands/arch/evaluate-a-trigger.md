---
description: "Only when · Evaluate whether an ADR trigger has fired"
---

# Only when · Evaluate whether an ADR trigger has fired

## Before you start

Read, in this order: `docs/architecture/README.md` (index and glossary), `docs/architecture/decisions.md`, then the files under **Read first** below. Load nothing else until a task needs it. Work from a task list and keep it updated.

## Hard rules

- Everything in an account is generated from the catalog. Never hand-edit a rule, bucket, route, role, alarm or contract; change the catalog or the generator.
- Do not introduce Athena, Glue, Iceberg, Kinesis, Temporal, Step Functions outside the saga module, a central gateway, CloudFront, a Schema Registry or a data platform account. If you believe an ADR trigger has fired, stop and run `prompts/10-evaluate-a-trigger.md` instead.
- PII: every schema field carries `x-pii`. `indirect` travels in clear, `direct` is encrypted per subject in public events through the subject-key service, `special` never enters an event.
- Facts are events. One synchronous hop between domains, through a generated client. Never another domain's database or bucket.
- Tests before infrastructure: L0 contract (no infra) → L1 domain-local (LocalStack + pinned `platform-local`) → L2 platform. Never depend on another domain's code or a shared environment.
- Small commits with the ADR or doc section they implement named in the message. If a decision cannot be undone and the docs do not settle it, stop and ask, giving the options and your recommendation.

**Read first:** `docs/architecture/decisions.md` · `the relevant docs/architecture/adr/ADR-*.md` · `docs/architecture/trade-offs.md`

## Goal

Decide, with evidence, whether a request or symptom is one of the named triggers that reopens a decision — and if it is not, say what the current defaults already offer.

## Procedure

1. Restate the request or symptom in one sentence. Identify the ADR(s) it touches.
2. Quote the ADR's `revisit_when` entries. For each, state whether it has fired and the evidence: metrics, costs, a failed exit criterion, a regulatory requirement, a measured limit. "It would be nicer" is not evidence.
3. If none has fired: answer with the cheapest way to meet the need inside current defaults (a read model, a FIFO target, a transformer, a reader role, a contract overlay), and stop.
4. If one has fired: write `adr/ADR-NNN-<slug>.md` with `status: proposed`, `supersedes: ADR-xxx`, the evidence, what changes, what explicitly does not change (buckets, contracts, conventions, tests), the new trade-offs, and an implementation plan that reuses the same generated files and contracts. Update `decisions.md` in the same PR with the new default and its own `revisit_when`.
5. Never implement the change in the same PR as the ADR.

## Output

Either "no trigger fired — do this instead" with the alternative, or the proposed ADR and a plan. Nothing in between.

## Report back

Finish with: what was built (paths); each exit criterion with its evidence (test names and output, plan summaries, screenshots of the catalog where relevant); what you deliberately did not do and why; any ADR trigger you think is close to firing.
