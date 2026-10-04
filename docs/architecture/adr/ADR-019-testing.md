---
id: ADR-019
title: "Testing"
status: accepted
date: 2026-10-04
reviewed: changed-after-review
revisit_when:
  - "Never a shared integration environment for automated tests"
  - "If a test needs another domain's code, the contract is wrong"
---

# ADR-019 · Testing

## Decision

Contract tests with no infra; domain-local LocalStack with the versioned platform stub and Prism mocks; platform tests with synthetic events **run nightly against a real AWS sandbox account** as well as LocalStack; one smoke event and one smoke call per domain in prod.

## Revisit only when

Never a shared integration environment for automated tests. If a test needs another domain's code, the contract is wrong.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Update `decisions.md` in the same PR. Generated IaC follows the catalog, never the other way round.
