---
step: cross-cutting
title: "Operation · Add an API operation (command or query)"
read_first:
  - docs/architecture/conventions.md
  - docs/architecture/adr/ADR-004-api-contracts.md
  - docs/architecture/adr/ADR-005-api-hosting.md
  - docs/architecture/testing.md
---

# Operation · Add an API operation (command or query)

{{> before-you-start}}

{{> hard-rules}}

**Read first:** {{read_first}}

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

{{> report-back}}
