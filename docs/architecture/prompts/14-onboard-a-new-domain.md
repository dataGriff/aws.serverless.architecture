---
step: cross-cutting
title: "Operation · Onboard a new domain"
read_first:
  - docs/architecture/README.md
  - docs/architecture/roadmap.md
  - docs/architecture/accounts.md (from step 4)
  - docs/architecture/testing.md
---

# Operation · Onboard a new domain

{{> before-you-start}}

{{> hard-rules}}

**Read first:** {{read_first}}

## Goal

A new domain live in nonprod in a day, by catalog PR plus accounts, with nothing hand-made.

## Steps

1. Catalog PR: `domains/<name>` with owners and CODEOWNERS; first service with its OpenAPI (one command, one query); first public and first internal event with schemas, `x-pii`, examples and the overlay; a channel for the API only (`x-bus` names the bus; the per-event channels are generated).
2. Accounts: nonprod and prod for the domain, OIDC roles for its pipeline, environment pins pointing at the current catalog tag; DNS delegation for `<name>.api.example.com`.
3. Run `catalog-gen build` for every environment: expect the bus, bucket pair, the RAM share of central to the new account, its subscribers (from `receives[]`) and Firehose subscriber on central, compactor, reader role, alarms, REST API body, DNS record, and the domain's ODCS contracts. The platform pipeline applies the central-side changes in manifest order; the domain pipeline applies its own.
4. Domain repo from `templates/domain-repo/` (lifted into its own repository): `platform-local` and `platform_testing` pinned, Taskfile, the L0/L1 suites, Schemathesis, Prism for any upstream API it calls.
5. Smokes: `SmokeTest.v1` into its bronze, `GET /v1/health` through the authorizer.
6. First consumer in another domain subscribes with a `receives[]` PR, pinned.

## Done when

Smokes green; the domain's L1 suite green with no other domain present; its events and operations visible in the catalog with contracts; no resource in its accounts that `catalog-gen check` does not account for.

{{> report-back}}
