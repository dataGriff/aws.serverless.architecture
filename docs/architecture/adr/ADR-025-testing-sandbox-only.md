---
id: ADR-025
title: "Testing — what LocalStack proves, what only the sandbox can"
status: accepted
supersedes: ADR-019
date: 2026-10-04
accepted: 2026-10-04
evidence:
  - spikes/B-localstack-buses-end-to-end/findings.md
  - spikes/D-custom-event-bus/findings.md
revisit_when:
  - "Never a shared integration environment for automated tests"
  - "If a test needs another domain's code, the contract is wrong"
  - "LocalStack emulates `eventsv2` → move the subscriber tests back into L1"
---

# ADR-025 · Testing — what LocalStack proves, what only the sandbox can

## Why ADR-019 is reopened

ADR-019 treated the nightly sandbox run as belt and braces. Spike B showed it is the **only** test for several mechanisms the design depends on, and that LocalStack can return green for the wrong reason:

| Mechanism | LocalStack Community 4.14 | LocalStack licensed 2026.9 | Real AWS |
| --- | --- | --- | --- |
| second bus-to-bus hop | delivered | delivered | **refused** (`THIRD_ACCOUNT_HOP_DETECTED`) |
| target DLQ record | never written | never written | written, with `ERROR_CODE` |
| SQS / bus resource policies, IAM roles | not enforced | enforced with `ENFORCE_IAM=1` | enforced |
| `StartReplay` | 500 | 500 | n/a (ADR-023) |
| input transformer on a bus target | accepted, event dropped | rejected like AWS | rejected |
| Firehose partitioning / quarantine / transform contract | not honoured | not honoured | honoured |
| Custom Event Bus (`eventsv2`) | none | none | — |

## Decision

Four layers, with an explicit **sandbox-only** list.

- **L0 · Contract (no infra).** Unchanged.
- **L1 · Domain-local (LocalStack, licensed image with `ENFORCE_IAM=1`, pinned).** The domain's Classic bus, outbox relay, forward rule to a **Classic stub central**, and the consumer's subscriptions rendered as Classic rules on the stub targeting the consumer's queue — the same filter and the same target as the real subscriber, one hop. Archive via the Lambda shim (ADR-024). Prism mocks for APIs. LocalStack `4.14.0` is the documented no-licence fallback and cannot enforce IAM.
- **L2 · Platform (real AWS sandbox, nightly and per-branch).** The Custom central bus, RAM sharing, subscribers, FIFO, dedup, replay, DLQ records, Firehose, IAM — everything in the sandbox-only list. Synthetic events from catalog schemas. An ephemeral stack per branch is cheap enough (Spikes B and D: pennies) to run on every platform PR, not only nightly.
- **L3 · Smoke (prod).** Unchanged.

**Sandbox-only (never trusted from LocalStack):** bus-to-bus hop limits and loop detection; any DLQ record and its latency; resource-policy and IAM evaluation; replay; Firehose buffering, partitioning, `processing-failed/` and the transform payload contract; everything about the Custom Event Bus. Tests for these carry a `sandbox` marker and are excluded from `task test` locally; CI fails if a `sandbox`-marked test is asserted green against LocalStack.

**Drift gates in L1 (Spike C).** `task test` fails before any delivery test when the catalog is ahead of `generated/` (`catalog-gen check`) or `generated/` is ahead of the applied environment (`terraform plan -detailed-exitcode` is non-empty), and a local scan asserts every rule on every local bus equals its generated file — the nightly guardrail run per PR. The `platform-local` rendering reads the same `subscribers/*.json` the AWS rendering does; there is no separate Classic twin file to drift.

**LocalStack results are recorded, not assumed.** Where the emulator diverges, the test is `xfail(strict=True)` on LocalStack with the reason, so a fix in LocalStack surfaces as an unexpected pass.

## What does not change

No shared integration environment; no test depends on another domain's code; `platform_testing` helpers; the smoke events.

## New trade-offs

- Two renderings of `receives[]` (Classic rule locally, subscriber on AWS) can drift; the generator snapshot tests both from one input.
- A per-branch sandbox stack needs credentials in CI and a teardown that always runs; cost is negligible, blast radius is the sandbox account.
- Licensed LocalStack is a paid dependency for every domain repo's L1 — accepted 2026-10-04; the token is supplied from the developer's or CI's environment, never from the repo (`docker-compose.licensed.yml` in Spike B shows the pattern).

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Update `decisions.md` in the same PR. Generated IaC follows the catalog, never the other way round.
