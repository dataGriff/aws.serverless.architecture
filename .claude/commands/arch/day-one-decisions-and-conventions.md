---
description: "Day one · Ratify decisions, encode conventions"
---

# Day one · Ratify decisions, encode conventions

## Before you start

Read, in this order: `docs/architecture/README.md` (index and glossary), `docs/architecture/decisions.md`, then the files under **Read first** below. Load nothing else until a task needs it. Work from a task list and keep it updated.

## Hard rules

- Everything in an account is generated from the catalog. Never hand-edit a rule, bucket, route, role, alarm or contract; change the catalog or the generator.
- Do not introduce Athena, Glue, Iceberg, Kinesis, Temporal, Step Functions outside the saga module, a central gateway, CloudFront, a Schema Registry or a data platform account. If you believe an ADR trigger has fired, stop and run `prompts/10-evaluate-a-trigger.md` instead.
- PII: every schema field carries `x-pii`. `indirect` travels in clear, `direct` is encrypted per subject in public events through the subject-key service, `special` never enters an event.
- Facts are events. One synchronous hop between domains, through a generated client. Never another domain's database or bucket.
- Tests before infrastructure: L0 contract (no infra) → L1 domain-local (LocalStack + pinned `platform-local`) → L2 platform. Never depend on another domain's code or a shared environment.
- Small commits with the ADR or doc section they implement named in the message. If a decision cannot be undone and the docs do not settle it, stop and ask, giving the options and your recommendation.

**Read first:** `docs/architecture/trade-offs.md` · `docs/architecture/conventions.md` · `docs/architecture/pii.md` · `docs/architecture/data-contracts.md` · `docs/architecture/adr/ (all)`

## Goal

Turn the architecture docs into this organisation's ratified baseline, and make every convention machine-checkable so later steps can enforce it rather than ask for it.

## Scope

1. **Localise, don't redesign.** Work through `platform.yaml` at the repo root: it names every placeholder (DNS suffix, schema `$id` base, organisation name, owner emails, the IdP, the sandbox account, the region) and where each is used. Set each `value`, replace the placeholder text wherever `task localise:report` shows it, and leave `orders`/`payments` alone — they are the worked example and are replaced by onboarding real domains, not by search-and-replace. If a value is not in the repo, ask — do not invent organisational facts. The region is a decision (ADR-020, ADR-021), not a free parameter. Set each ADR to `status: accepted` with today's date and the names of who ratified it. If a default has to change, do not edit the ADR: write a superseding ADR using `prompts/10-evaluate-a-trigger.md`.
2. **Encode the conventions** under `conventions/`:
   - `envelope.schema.json` — JSON Schema for the `detail` envelope (`eventId`, `occurredAt`, `correlationId`, `causationId`, `aggregateId`, `aggregateVersion`, `replay`).
   - `x-pii.metaschema.json` — a meta-schema that rejects any property without `x-pii` and restricts it to `none | indirect | direct | special`; plus `x-external` boolean on API operations.
   - `spectral.yaml` — one rule per API convention: `/v{n}` path version, `problem+json` errors, `Idempotency-Key` required on POST, `X-Correlation-Id` accepted and echoed, cursor pagination, security scheme declared, `x-eventcatalog-message-type` present, `Sunset`/`Deprecation` headers on deprecated versions.
   - `names.md` — bus, bucket, subdomain, role and stream names with one example each.
   - `pii-classes.md` — the classification table from `pii.md` with examples drawn from this business, reviewed by whoever owns data protection.
3. **Quotas.** `scripts/check-quotas.sh` that reads EventBridge PutEvents, invocation and rules-per-bus quotas for the region via `aws service-quotas`, prints current vs the estimate in `roadmap.md`, and drafts the raise requests.
4. **Trade-offs** recorded as an appendix ADR (`ADR-000-accepted-trade-offs.md`) so nobody has to rediscover them.

## Done when

- `task localise:check` passes, and `grep -r "TODO\|TBD" docs conventions` finds nothing.
- `spectral lint` on `conventions/fixtures/*.yaml` fails exactly once per fixture, each fixture violating one rule, with a message that names the convention.
- The meta-schema rejects `conventions/fixtures/unclassified-field.schema.json` and accepts the envelope schema.
- `scripts/check-quotas.sh` runs against the sandbox account and prints the comparison.
- Every ADR has a status, a date and ratifiers; `decisions.md` still matches the ADR set.

## Report back

Finish with: what was built (paths); each exit criterion with its evidence (test names and output, plan summaries, screenshots of the catalog where relevant); what you deliberately did not do and why; any ADR trigger you think is close to firing.
