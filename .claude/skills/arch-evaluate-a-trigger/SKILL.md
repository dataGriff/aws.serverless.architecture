---
name: arch-evaluate-a-trigger
description: Use whenever someone asks for a service or change the decisions table does not permit (Athena, Glue, Iceberg, Kinesis, Temporal, Step Functions outside the saga, CloudFront, a Schema Registry, a data platform account, a second region, a different bus topology): decide with evidence whether an ADR's revisit_when trigger has fired and either propose a superseding ADR or name the alternative inside current defaults. Triggers on 'can we use', 'why can't we', 'should we add', 'is the trigger fired', 'new ADR'.
---

# Only when · Evaluate whether an ADR trigger has fired

## Before you start

Read, in this order: `docs/architecture/README.md` (index and glossary), `docs/architecture/decisions.md`, then the files under **Read first** below. Load nothing else until a task needs it. When a task needs what the catalog says (which services send or receive an event, which fields are `direct`, who owns what, what a change would break), ask the catalog rather than grepping it: through its MCP server when one is configured (`AGENTS.md`, *Querying the catalog*), otherwise through the published `llms.txt` and `schemas.txt`; open catalog files only to edit them. Work from a task list and keep it updated.

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
4. If one has fired: copy `docs/architecture/adr/TEMPLATE.md` to `adr/ADR-NNN-<slug>.md` and fill it in: `status: proposed`, `supersedes: ADR-xxx`, the evidence, what changes, what explicitly does not change (buckets, contracts, conventions, tests), the new trade-offs, and an implementation plan that reuses the same generated files and contracts. Add a CHANGELOG line when it is accepted. Give it `concern:` and `decision:` in its frontmatter and its own `revisit_when`, then `task adr:build` renders its row into `decisions.md` in the same PR (`task adr:check` must pass).
5. Never implement the change in the same PR as the ADR.

## Output

Either "no trigger fired — do this instead" with the alternative, or the proposed ADR and a plan. Nothing in between.

## Report back

Finish with: what was built (paths); each exit criterion with its evidence (test names and output, plan summaries, screenshots of the catalog where relevant); what you deliberately did not do and why; any ADR trigger you think is close to firing.
