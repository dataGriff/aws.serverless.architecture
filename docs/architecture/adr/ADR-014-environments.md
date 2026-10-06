---
id: ADR-014
title: "Environments"
concern: "Environments"
decision: >-
  Two account tiers per domain and for the platform: **nonprod** (env-suffixed `dev` and `test` inside it) and **prod**. The catalog is released by tag and **each environment pins a tag**; promotion is a PR that bumps the pin, so a new event version reaches dev before prod by construction. `test` is where every domain deploys for UAT and exploration — automated tests never depend on it.
status: accepted
date: 2026-10-04
reviewed: changed-after-review
revisit_when:
  - "A regulator asks for evidence from an integrated environment → formalise `test` as that environment with its own smoke suite"
  - "Many teams → account per env per domain"
---

# ADR-014 · Environments

## Decision

Two account tiers per domain and for the platform: **nonprod** (env-suffixed `dev` and `test` inside it) and **prod**. The catalog is released by tag and **each environment pins a tag**; promotion is a PR that bumps the pin, so a new event version reaches dev before prod by construction. `test` is where every domain deploys for UAT and exploration — automated tests never depend on it.

## Revisit only when

A regulator asks for evidence from an integrated environment → formalise `test` as that environment with its own smoke suite. Many teams → account per env per domain.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Set its `concern:`, `decision:` and `revisit_when` and run `task adr:build` in the same PR. Generated IaC follows the catalog, never the other way round.
