---
id: ADR-023
title: "Replay — bus retention and point-in-time subscribers"
status: proposed
supersedes: ADR-008
date: 2026-10-04
evidence:
  - spikes/D-custom-event-bus/findings.md
  - spikes/B-localstack-buses-end-to-end/findings.md
revisit_when:
  - "Replay older than the retention window → an S3 → bus replayer that publishes with `DeduplicationId=eventId` and lets the subscriber transformer set `replay: true`"
  - "A replay must not re-deliver to live consumers → `EndPoint` on the point-in-time subscriber and a dedicated target; never pause the live subscriber"
---

# ADR-023 · Replay — bus retention and point-in-time subscribers

## Why ADR-008 is reopened

ADR-008 relied on the Classic native archive and `StartReplay`. With central as a Custom Event Bus (ADR-021) there is no archive: **the bus retains events**, and "there is no separate replay API: a subscriber reads retained events from its starting position" ([docs](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-custom-bus-replay.html)). Spike D proved it: a subscriber created after the fact with `StartingPosition=POINT_IN_TIME` re-delivered the earlier event with `SystemMetadata` field `aws:DeliveryType` = `REPLAY` (in JSONata: `` $events.SystemMetadata.`aws:DeliveryType` ``) and identical `Data` (`test_replay_via_point_in_time_subscriber_marks_events_replay`).

Spike B also showed the Classic path could not be tested locally anyway: LocalStack's `StartReplay` returns a 500 in both editions and leaves the replay in `STARTING` forever.

## Decision

**Retention on central is 30 days** (`StorageConfiguration.RetentionPeriodInDays`), matching ADR-008's window. The **operational replay** is a `POINT_IN_TIME` subscriber created by the consumer that needs it, in its own account, with the same filter as its live subscriber, `PointType=TIMESTAMP` and an `EndPoint`, targeting the consumer's own queue or function. Replayed events carry `aws:DeliveryType=REPLAY`, which the generated transformer surfaces as `replay: true` (ADR-022); side-effecting consumers skip them, as before. S3 bronze remains for analytics and audit, never for re-driving consumers.

`platform_testing.replay(event)` in the test package drives this: create the subscriber, wait for `RUNNING`, assert at the target, delete it.

## Constraints that bind the runbook (Spike D)

- `StartingPoint` must be **at least 5 minutes in the past** (`InvalidInputException`). Replay-after-incident is fine; "replay the last 30 seconds" is not.
- A replay has a **startup delay** then runs at live speed; Spike D saw delivery inside 3 minutes. Allow for it before concluding it failed.
- **One subscriber create/delete at a time per bus**; a replay drill queues behind any other subscriber change.
- `RetentionWindowStartTime` on `DescribeEventBus` is the earliest readable point; on a new bus it is the creation time.
- Replay subscribers are ordinary subscribers: they need the delivery role and a DLQ, and they count against the subscriber quota while they exist. Delete them when done.

## What does not change

The `replay` flag's meaning to consumers; bronze/silver; the quarterly replay drill into `test`; the S3 replayer as the only path beyond the window.

## New trade-offs

- Replay re-reads *everything* the filter matches from the point in time, so a replay for one consumer is scoped by that consumer's filter, not by the platform. Finer scoping (one aggregate) is a `DATA` filter on the replay subscriber.
- Retention is billed per GB-month; 30 days of public events is the cost ceiling to model.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Update `decisions.md` in the same PR. Generated IaC follows the catalog, never the other way round.
