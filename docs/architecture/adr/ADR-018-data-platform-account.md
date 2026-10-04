---
id: ADR-018
title: "Data platform account"
status: accepted
date: 2026-10-04
reviewed: unchanged
revisit_when:
  - "Analysts need their own IAM boundary, gold needs its own storage, or the platform team shouldn't own analytics → create it; move roles, views, gold"
  - "Buckets stay"
---

# ADR-018 · Data platform account

## Decision

None. Reader roles live in the platform account.

## Revisit only when

Analysts need their own IAM boundary, gold needs its own storage, or the platform team shouldn't own analytics → create it; move roles, views, gold. Buckets stay.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Update `decisions.md` in the same PR. Generated IaC follows the catalog, never the other way round.
