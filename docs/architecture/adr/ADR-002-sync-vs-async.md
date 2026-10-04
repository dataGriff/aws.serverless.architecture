---
id: ADR-002
title: "Sync vs async"
status: accepted
date: 2026-10-04
reviewed: unchanged
revisit_when:
  - "A query that would fan out across domains → a read model built from events in the asking domain (CQRS)"
  - "A command needing multi-step coordination → a saga, below"
---

# ADR-002 · Sync vs async

## Decision

Facts are events. A query or command that needs an answer *now* is an API call: one synchronous hop through a client generated from the provider's catalog spec, with timeouts, retries, a circuit breaker and a consumer-side projection. `X-Correlation-Id` in → `correlationId` on every event out. A CI lint on the catalog graph fails any sync chain deeper than one hop.

## Revisit only when

A query that would fan out across domains → a read model built from events in the asking domain (CQRS). A command needing multi-step coordination → a saga, below.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Update `decisions.md` in the same PR. Generated IaC follows the catalog, never the other way round.
