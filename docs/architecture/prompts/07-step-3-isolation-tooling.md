---
step: 3
when: >-
  Use for roadmap step 3 when extracting platform-local as a versioned module, publishing the platform_testing package, pinning upstream APIs as Prism mocks, and running the erasure drill and the nightly L2 sandbox run. Triggers on 'platform-local', 'platform_testing', 'test in isolation', 'erasure drill'.
title: "Step 3 · platform-local, platform_testing and the erasure drill"
read_first:
  - docs/architecture/testing.md
  - docs/architecture/roadmap.md (Step 3)
  - docs/architecture/pii.md
  - docs/architecture/adr/ADR-025-testing-sandbox-only.md
---

# Step 3 · platform-local, platform_testing and the erasure drill

{{> before-you-start}}

{{> hard-rules}}

**Read first:** {{read_first}}

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

{{> report-back}}
