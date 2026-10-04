---
id: ADR-006
title: "Event shape"
status: superseded
superseded_by: "ADR-022 — the only revisit path (input transformer on the forward rule) is unavailable on bus targets"
date: 2026-10-04
reviewed: unchanged
revisit_when:
  - "Internal vocabulary or unstable fields in a public event → input transformer on the forward rule, or a distinct public event with `derivedFrom`"
---

# ADR-006 · Event shape

## Decision

Forwarded unchanged; the catalog marks it public. The envelope gains `replay: boolean`.

## Revisit only when

Internal vocabulary or unstable fields in a public event → input transformer on the forward rule, or a distinct public event with `derivedFrom`.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Update `decisions.md` in the same PR. Generated IaC follows the catalog, never the other way round.
