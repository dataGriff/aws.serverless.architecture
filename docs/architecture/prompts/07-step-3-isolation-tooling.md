---
step: 3
title: "Step 3 · platform-local, platform_testing and the erasure drill"
read_first:
  - docs/architecture/testing.md
  - docs/architecture/roadmap.md (Step 3)
  - docs/architecture/pii.md
  - docs/architecture/adr/ADR-019-testing.md
---

# Step 3 · platform-local, platform_testing and the erasure drill

## Before you start

Read, in this order: `docs/architecture/README.md` (index and glossary), `docs/architecture/decisions.md`, then the files under **Read first** below. Load nothing else until a task needs it. Work from a task list and keep it updated.

## Hard rules

- Everything in an account is generated from the catalog. Never hand-edit a rule, bucket, route, role, alarm or contract; change the catalog or the generator.
- Do not introduce Athena, Glue, Iceberg, Kinesis, Temporal, Step Functions outside the saga module, a central gateway, CloudFront, a Schema Registry or a data platform account. If you believe an ADR trigger has fired, stop and run `prompts/10-evaluate-a-trigger.md` instead.
- PII: every schema field carries `x-pii`. `indirect` travels in clear, `direct` is encrypted per subject in public events through the subject-key service, `special` never enters an event.
- Facts are events. One synchronous hop between domains, through a generated client. Never another domain's database or bucket.
- Tests before infrastructure: L0 contract (no infra) → L1 domain-local (LocalStack + pinned `platform-local`) → L2 platform. Never depend on another domain's code or a shared environment.
- Small commits with the ADR or doc section they implement named in the message. If a decision cannot be undone and the docs do not settle it, stop and ask, giving the options and your recommendation.

**Read first:** `docs/architecture/testing.md` · `docs/architecture/roadmap.md (Step 3)` · `docs/architecture/pii.md` · `docs/architecture/adr/ADR-019-testing.md`

## Goal

Make isolation a product: a versioned stub any domain applies, a test helper package any domain imports, and the proofs that a domain can be tested — and a subject erased — with nobody else present.

## Build

- `platform-local` extracted as a versioned module: Classic stub central, the domain's `receives[]` as subscriber-shaped rules to its own queues, the archive shim (ADR-024), compactor, the domain's bucket pair, a probe queue, and a local `subject-keys` instance.
- `platform_testing` (Python package, published): `assert_published`, `assert_not_published`, `assert_quarantined`, `duck()`, `prism(service, version)`, `replay(event)`, `erase_subject(id)`, `decrypt_as(role)`, pytest fixtures for LocalStack, Terraform apply, outbox drain and catalog checkout at a pin.
- Payments calls the orders API through the generated client; its L1 tests run against the Prism mock of orders at a pinned catalog version; the pin lives in one file.
- Erasure drill test: delete a subject key → the ungranted role never could read; the granted role now receives "erased"; `SubjectErased` arrives in both domains; a consumer that persisted decrypted data runs its purge.
- Nightly L2 workflow running the platform suite in the real sandbox account via OIDC.

## Done when

- Bumping the orders pin in payments is the only way payments sees a new orders field, and the bump fails loudly if orders broke compatibility.
- The erasure drill passes locally and in the sandbox.
- The nightly L2 run has completed green at least three nights running and its failures page an owner.

## Report back

Finish with: what was built (paths); each exit criterion with its evidence (test names and output, plan summaries, screenshots of the catalog where relevant); what you deliberately did not do and why; any ADR trigger you think is close to firing.
