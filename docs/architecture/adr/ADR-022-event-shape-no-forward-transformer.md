---
id: ADR-022
title: "Event shape — forwarded unchanged; transforms only on the consumer's subscriber"
status: proposed
supersedes: ADR-006
date: 2026-10-04
evidence:
  - spikes/B-localstack-buses-end-to-end/findings.md
  - spikes/D-custom-event-bus/findings.md
revisit_when:
  - "Internal vocabulary or unstable fields in a public event → a distinct public event with `derivedFrom`, published by the producer"
  - "A consumer needs a different shape → a `JSONATA` transformer on *its own* subscriber, declared in its `receives[]` entry; never on the forward rule"
---

# ADR-022 · Event shape — forwarded unchanged; transforms only on the consumer's subscriber

## Why ADR-006 is reopened

ADR-006's only revisit path was "an input transformer on the forward rule". That path does not exist:

- AWS: "`Input`, `InputPath`, and `InputTransformer` are not available with `PutTarget` if the target is an event bus of a different AWS account" ([PutTargets](https://docs.aws.amazon.com/eventbridge/latest/APIReference/API_PutTargets.html)).
- Spike B on licensed LocalStack 2026.9: `PutTargets` with an input transformer on a bus target is rejected with `ValidationException: Modifying the input for target ... is not supported` — same-account included. Community 4.14 accepts it and then silently drops every event (`test_input_transformer_on_bus_target`, `task probe` row `InputTransformer on a bus target`).

## Decision

Events are **forwarded unchanged** from the domain bus to central; the catalog marks them public. The envelope keeps `eventId`, `occurredAt`, `correlationId`, `causationId`, `aggregateId`, `aggregateVersion`, `replay`.

The `replay` flag is **set by the subscriber, not the producer**: the generated subscriber uses a `JSONATA` transformer that re-emits the Classic envelope with `detail.replay = ($events.SystemMetadata."aws:DeliveryType" = "REPLAY")`, so consumers keep one payload shape for live and replayed events. Until that expression is verified in the sandbox the subscriber delivers `RAW` (Spike D: byte-identical to the Classic envelope) and `replay` is absent, meaning `false`.

Reshaping for a consumer is the consumer's business: a `JSONATA` transformer on its own subscriber, declared in its `receives[]` entry so the catalog shows it. Reshaping for everyone is a new public event with `derivedFrom`, published by the producer.

## What does not change

Envelope fields, `source`/`detail-type` conventions, versioning (`.v2` is a new event), PII classification (ADR-007), the forward rule.

## New trade-offs

- A consumer-side transformer is invisible to other consumers and to the archive, which is the point, but it means the archive always holds the producer's shape.
- JSONata expressions are validated for syntax at create time and evaluated at delivery; an expression that throws fails that delivery into the DLQ. The generator emits only the one audited expression above.

## Implementation plan

1. Spike D follow-up: verify the `replay`-injecting JSONata expression on a subscriber in the sandbox (`WITH_METADATA` already exposes `aws:DeliveryType`; `test_replay_via_point_in_time_subscriber_marks_events_replay`).
2. Generator: `receives[].transform` (optional JSONata) → `Transformer.Type=JSONATA`; default emits the replay-flag expression; catalog page shows the transform.
3. Remove "input transformer on the forward rule" from conventions and the module library (`bus-forward-rule` loses `input_transformer`).

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Update `decisions.md` in the same PR. Generated IaC follows the catalog, never the other way round.
