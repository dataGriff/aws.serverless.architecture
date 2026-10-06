---
step: 4
when: >-
  Use for roadmap step 4: real AWS accounts, nonprod then prod — the Custom Event Bus shared by RAM, subscribers applied in manifest order, bucket pairs with CMKs and Object Lock, DNS, WAF, smokes, environment pins, the replay runbook. Triggers on 'real accounts', 'nonprod', 'prod', 'step 4', 'RAM share', 'go live'.
title: "Step 4 · Real accounts — nonprod, then prod"
read_first:
  - docs/architecture/roadmap.md (Step 4)
  - docs/architecture/adr/ADR-005-api-hosting.md
  - docs/architecture/adr/ADR-023-replay-retention.md
  - docs/architecture/adr/ADR-010-bucket-location-protection.md
  - docs/architecture/adr/ADR-014-environments.md
  - docs/architecture/adr/ADR-020-dr.md
  - docs/architecture/pii.md
---

# Step 4 · Real accounts — nonprod, then prod

{{> before-you-start}}

{{> hard-rules}}

**Read first:** {{read_first}}

## Goal

Prove in real AWS the things LocalStack cannot: IAM, resource policies, DNS, encryption, cross-account delivery, real authentication, WAF and replay. Nonprod first, prod only by pin bump.

## Build

- Accounts: platform and one per domain, nonprod and prod tiers; CI assumes roles via OIDC; no long-lived keys anywhere.
- From the generator, applied in the manifest's order by the platform pipeline: the Custom Event Bus central in eu-west-1 shared by RAM to each domain account (publish for forward-rule roles, subscribe for consumers); each domain's subscribers, applied one at a time per bus; bucket pairs with CMK, Object Lock on bronze, versioning, CRR in prod; grants to each domain's own account and to its reader role; the subject-key service; 30-day retention on central; alarms and dashboards.
- Domains: DNS delegated per domain; REST APIs deployed from generated bodies with the platform JWT issuer or IAM auth; WAF attached where the catalog marks `x-external`.
- Post-deploy smokes: `{domain}.SmokeTest.v1` → own bronze within the Firehose buffer; `GET /v1/health` through the real authorizer.
- Environment pins: each environment pins a catalog tag; promotion is a PR that bumps the pin; `test` is where every domain deploys for UAT.
- Replay runbook: a documented, rehearsed procedure using a `POINT_IN_TIME` subscriber (start ≥ 5 min in the past, `EndPoint`, the consumer's own target) into `test` (ADR-023).

## Done when

- Both smokes are green in every account on every deploy; a new event version reaches dev, then test, then prod by pin bumps only.
- Negative tests pass: a domain cannot read another domain's bucket pair; a reader role cannot write; an unauthenticated call is rejected at the gateway; a malformed webhook is dropped by WAF before the handler; a non-decryptor role cannot fetch a subject key.
- A point-in-time replay into `test` re-drives a consumer with `replay: true` and no side effects; a subscriber in a domain account receives from the RAM-shared central.
- The account map, role names and break-glass procedure are documented in `docs/architecture/accounts.md`.

{{> report-back}}
