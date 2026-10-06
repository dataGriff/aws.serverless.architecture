---
id: ADR-016
title: "Lifecycle"
concern: "Lifecycle"
decision: >-
  Events and API versions carry `deprecated` and `sunset` dates in the catalog. A producer **dual-publishes** old and new versions until sunset; APIs send `Sunset`/`Deprecation` headers. CI fails when any `receives[]` or client pin still points at a version past its sunset.
status: accepted
date: 2026-10-04
reviewed: changed-after-review
revisit_when:
  - "Never"
---

# ADR-016 · Lifecycle

## Decision

Events and API versions carry `deprecated` and `sunset` dates in the catalog. A producer **dual-publishes** old and new versions until sunset; APIs send `Sunset`/`Deprecation` headers. CI fails when any `receives[]` or client pin still points at a version past its sunset.

## Revisit only when

Never.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Set its `concern:`, `decision:` and `revisit_when` and run `task adr:build` in the same PR. Generated IaC follows the catalog, never the other way round.
