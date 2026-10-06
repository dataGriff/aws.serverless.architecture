---
name: arch-architecture-review
description: Use when reviewing a PR or a design against the architecture: finds what contradicts a decision, convention, PII rule, data contract or testing layer and cites the ADR or doc section; outputs a findings table and approve / approve-with-fixes / block. Triggers on 'architecture review', 'review this PR against the decisions', 'does this follow the conventions'.
---

# Cross-cutting · Review a change against the architecture

## Before you start

Read, in this order: `docs/architecture/README.md` (index and glossary), `docs/architecture/decisions.md`, then the files under **Read first** below. Load nothing else until a task needs it. When a task needs what the catalog says (which services send or receive an event, which fields are `direct`, who owns what, what a change would break), ask the catalog rather than grepping it: through its MCP server when one is configured (`AGENTS.md`, *Querying the catalog*), otherwise through the published `llms.txt` and `schemas.txt`; open catalog files only to edit them. Work from a task list and keep it updated.

## Hard rules

- Everything in an account is generated from the catalog. Never hand-edit a rule, bucket, route, role, alarm or contract; change the catalog or the generator.
- Do not introduce Athena, Glue, Iceberg, Kinesis, Temporal, Step Functions outside the saga module, a central gateway, CloudFront, a Schema Registry or a data platform account. If you believe an ADR trigger has fired, stop and run `prompts/10-evaluate-a-trigger.md` instead.
- PII: every schema field carries `x-pii`. `indirect` travels in clear, `direct` is encrypted per subject in public events through the subject-key service, `special` never enters an event.
- Facts are events. One synchronous hop between domains, through a generated client. Never another domain's database or bucket.
- Tests before infrastructure: L0 contract (no infra) → L1 domain-local (LocalStack + pinned `platform-local`) → L2 platform. Never depend on another domain's code or a shared environment.
- Small commits with the ADR or doc section they implement named in the message. If a decision cannot be undone and the docs do not settle it, stop and ask, giving the options and your recommendation.

**Read first:** `docs/architecture/decisions.md` · `docs/architecture/conventions.md` · `docs/architecture/pii.md` · `docs/architecture/data-contracts.md` · `docs/architecture/testing.md`

## Goal

Review a PR or design the way the catalog CI would if it could read intent: find what contradicts a decision, convention, PII rule, contract or testing layer, and say precisely which one.

## Checklist

- Does it add a service or component the decisions table does not permit? Cite the row.
- Is anything in an account hand-written that the generator should emit? Name the file and the emitter.
- Events: `source`/`detail-type` conventions, envelope fields, `x-pii` on every field, `direct` encrypted in public events, `special` absent, `x-visibility` and `x-audience` set, version bump on breaking change, `deprecated.date` set on the old version (and `Sunset`/`Deprecation` headers on an old API version), `replay` honoured by side-effecting consumers.
- APIs: message type on every operation, `/v{n}`, `problem+json`, `Idempotency-Key` on commands, `X-Correlation-Id` propagated, `$ref` into `schemas/`, external routes marked, one synchronous hop.
- Data: silver columns match the ODCS contract; no `direct` field became a column; retention and classification declared; a new dataset has a contract before a consumer.
- Tests: L0 and L1 present and meaningful; no dependency on another domain's code or a shared environment; the step's exit criteria still hold.
- Trade-offs: does it silently remove one of the accepted trade-offs' mitigations (read-time dedupe, quarantine, pins, canary apply order)?

## Output

A table: finding · severity (block / fix before merge / note) · reference (ADR or doc section) · suggested change. End with approve, approve-with-fixes or block, and the one-line reason.

## Report back

Finish with: what was built (paths); each exit criterion with its evidence (test names and output, plan summaries, screenshots of the catalog where relevant); what you deliberately did not do and why; any ADR trigger you think is close to firing.
