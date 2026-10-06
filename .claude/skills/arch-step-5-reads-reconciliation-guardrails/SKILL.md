---
name: arch-step-5-reads-reconciliation-guardrails
description: Use for roadmap step 5: reader roles, DuckDB views across domain silvers, the nightly checks Lambda (reconciliation, drift, undocumented events, contract tests, freshness, ROPA, access review) and the first cross-domain question answered from silver. Triggers on 'reconciliation', 'nightly checks', 'read across domains', 'step 5', 'drift report'.
---

# Step 5 · Reading across domains, reconciliation and the nightly guardrails

## Before you start

Read, in this order: `docs/architecture/README.md` (index and glossary), `docs/architecture/decisions.md`, then the files under **Read first** below. Load nothing else until a task needs it. When a task needs what the catalog says (which services send or receive an event, which fields are `direct`, who owns what, what a change would break), ask the catalog rather than grepping it: through its MCP server when one is configured (`AGENTS.md`, *Querying the catalog*), otherwise through the published `llms.txt` and `schemas.txt`; open catalog files only to edit them. Work from a task list and keep it updated.

## Hard rules

- Everything in an account is generated from the catalog. Never hand-edit a rule, bucket, route, role, alarm or contract; change the catalog or the generator.
- Do not introduce Athena, Glue, Iceberg, Kinesis, Temporal, Step Functions outside the saga module, a central gateway, CloudFront, a Schema Registry or a data platform account. If you believe an ADR trigger has fired, stop and run `prompts/10-evaluate-a-trigger.md` instead.
- PII: every schema field carries `x-pii`. `indirect` travels in clear, `direct` is encrypted per subject in public events through the subject-key service, `special` never enters an event.
- Facts are events. One synchronous hop between domains, through a generated client. Never another domain's database or bucket.
- Tests before infrastructure: L0 contract (no infra) → L1 domain-local (LocalStack + pinned `platform-local`) → L2 platform. Never depend on another domain's code or a shared environment.
- Small commits with the ADR or doc section they implement named in the message. If a decision cannot be undone and the docs do not settle it, stop and ask, giving the options and your recommendation.

**Read first:** `docs/architecture/roadmap.md (Step 5)` · `docs/architecture/data-layer.md` · `docs/architecture/data-contracts.md` · `docs/architecture/generation-and-ci.md (nightly)` · `docs/architecture/adr/ADR-013-query-engine.md` · `docs/architecture/adr/ADR-015-observability.md`

## Goal

The first cross-domain answer from silver, and a nightly report that would have caught every fault we have so far imagined.

## Build

- Per-domain reader roles for people; DuckDB views that `UNION` deduped silver across the domain buckets, generated from the ODCS contracts; a Lambda runner for scheduled queries and a `task query` for laptops.
- Nightly checks Lambda: reconciliation (outbox counts vs bronze per domain per hour, tolerance from the contract); undocumented events (bronze vs catalog); quarantine volume split by schema failure vs clear-text `direct` PII; rule drift (account rules vs `generated/`); API drift (`get-export` vs catalog); partition completeness; bucket settings vs declarations; `datacontract test` per silver table and bronze envelope; freshness SLA; ROPA export; decryptor access review; erasure SLA.
- Results to alarms, a per-domain dashboard and catalog badges.
- Optional API access logs archived under `api/` in the domain's bronze bucket.

## Done when

- The nightly report exists, is clean, and each injected fault appears the next night: a hand-made rule, a hand-made route, a dropped event, a stale partition, a broken contract, a role with an unlisted decrypt grant.
- The first cross-domain question (orders × payments) is answered from silver by someone reading only the contracts.
- Adding a domain is demonstrably a catalog PR plus an account: do it for a fixture domain and time it.

## Report back

Finish with: what was built (paths); each exit criterion with its evidence (test names and output, plan summaries, screenshots of the catalog where relevant); what you deliberately did not do and why; any ADR trigger you think is close to firing.
