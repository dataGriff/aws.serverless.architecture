---
step: cross-cutting
title: "Cross-cutting · Review a change against the architecture"
read_first:
  - docs/architecture/decisions.md
  - docs/architecture/conventions.md
  - docs/architecture/pii.md
  - docs/architecture/data-contracts.md
  - docs/architecture/testing.md
---

# Cross-cutting · Review a change against the architecture

{{> before-you-start}}

{{> hard-rules}}

**Read first:** {{read_first}}

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

{{> report-back}}
