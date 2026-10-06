---
name: arch-onboard-a-new-domain
description: Use when bringing a new business domain onto the platform: its catalog entries, nonprod and prod accounts with OIDC roles, DNS delegation, the generated bus, bucket pair, subscribers and API, the domain repo from templates/domain-repo, smokes, the first consumer. Triggers on 'onboard a domain', 'new domain', 'add a team to the platform'.
---

# Operation · Onboard a new domain

## Before you start

Read, in this order: `docs/architecture/README.md` (index and glossary), `docs/architecture/decisions.md`, then the files under **Read first** below. Load nothing else until a task needs it. Work from a task list and keep it updated.

## Hard rules

- Everything in an account is generated from the catalog. Never hand-edit a rule, bucket, route, role, alarm or contract; change the catalog or the generator.
- Do not introduce Athena, Glue, Iceberg, Kinesis, Temporal, Step Functions outside the saga module, a central gateway, CloudFront, a Schema Registry or a data platform account. If you believe an ADR trigger has fired, stop and run `prompts/10-evaluate-a-trigger.md` instead.
- PII: every schema field carries `x-pii`. `indirect` travels in clear, `direct` is encrypted per subject in public events through the subject-key service, `special` never enters an event.
- Facts are events. One synchronous hop between domains, through a generated client. Never another domain's database or bucket.
- Tests before infrastructure: L0 contract (no infra) → L1 domain-local (LocalStack + pinned `platform-local`) → L2 platform. Never depend on another domain's code or a shared environment.
- Small commits with the ADR or doc section they implement named in the message. If a decision cannot be undone and the docs do not settle it, stop and ask, giving the options and your recommendation.

**Read first:** `docs/architecture/README.md` · `docs/architecture/roadmap.md` · `docs/architecture/accounts.md (from step 4)` · `docs/architecture/testing.md`

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

## Report back

Finish with: what was built (paths); each exit criterion with its evidence (test names and output, plan summaries, screenshots of the catalog where relevant); what you deliberately did not do and why; any ADR trigger you think is close to firing.
