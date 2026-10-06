---
description: "Operation · Add an API operation (command or query)"
---

# Operation · Add an API operation (command or query)

## Before you start

Read, in this order: `docs/architecture/README.md` (index and glossary), `docs/architecture/decisions.md`, then the files under **Read first** below. Load nothing else until a task needs it. When a task needs what the catalog says (which services send or receive an event, which fields are `direct`, who owns what, what a change would break), ask the catalog rather than grepping it: through its MCP server when one is configured (`AGENTS.md`, *Querying the catalog*), otherwise through the published `llms.txt` and `schemas.txt`; open catalog files only to edit them. Work from a task list and keep it updated.

## Hard rules

- Everything in an account is generated from the catalog. Never hand-edit a rule, bucket, route, role, alarm or contract; change the catalog or the generator.
- Do not introduce Athena, Glue, Iceberg, Kinesis, Temporal, Step Functions outside the saga module, a central gateway, CloudFront, a Schema Registry or a data platform account. If you believe an ADR trigger has fired, stop and run `prompts/10-evaluate-a-trigger.md` instead.
- PII: every schema field carries `x-pii`. `indirect` travels in clear, `direct` is encrypted per subject in public events through the subject-key service, `special` never enters an event.
- Facts are events. One synchronous hop between domains, through a generated client. Never another domain's database or bucket.
- Tests before infrastructure: L0 contract (no infra) → L1 domain-local (LocalStack + pinned `platform-local`) → L2 platform. Never depend on another domain's code or a shared environment.
- Small commits with the ADR or doc section they implement named in the message. If a decision cannot be undone and the docs do not settle it, stop and ask, giving the options and your recommendation.

**Read first:** `docs/architecture/conventions.md` · `docs/architecture/adr/ADR-004-api-contracts.md` · `docs/architecture/adr/ADR-005-api-hosting.md` · `docs/architecture/testing.md`

## Goal

Design-first: the operation exists in the catalog, is mocked and client-generated, before any handler is written.

## Steps

1. Catalog PR: add the operation to the service's OpenAPI with `x-eventcatalog-message-type: command | query`, the security scheme, `Idempotency-Key` on a command, `problem+json` responses, cursor pagination on list queries, bodies `$ref`-ing `schemas/`, `x-external: true` only if reachable from outside, `x-pii` on every body field. Spectral and `oasdiff` must pass; a breaking change is `/v{n+1}` with `Sunset` on the old.
2. Run `catalog-gen build`; expect exactly: the `commands/` or `queries/` page for the operation, one route, one validator, one integration, authorizer binding, one client method, Prism serves the operation from examples, Schemathesis covers it, a WAF association if external.
3. Consumers can start now against Prism at the pinned catalog version.
4. Handler: commands check the idempotency store, do the state change and the outbox write in one transaction, return `problem+json` on error; queries read a model, never call another domain synchronously beyond one hop.
5. Tests: handler unit tests from the spec examples; Schemathesis through gateway validation in L1; `test_gateway_rejects_invalid_body`; a command's event asserted via `assert_published` with the same `correlationId`.

## Done when

Spec merged first, generated artefacts reviewed, consumers unblocked by the mock, handler conformant, and the operation page in the catalog shows its callers.

## Report back

Finish with: what was built (paths); each exit criterion with its evidence (test names and output, plan summaries, screenshots of the catalog where relevant); what you deliberately did not do and why; any ADR trigger you think is close to firing.
