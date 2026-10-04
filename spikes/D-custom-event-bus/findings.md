# Spike D — findings: EventBridge Custom Event Bus as the central bus

Run on 2026-10-04 in **eu-west-1** against the sandbox account (the Custom Event Bus has no eu-west-2 endpoint). Terraform 1.9.8 with `hashicorp/awscc` 1.104.0 for the bus and subscribers and `hashicorp/aws` 6.67 for queues, roles and the Classic bus; boto3 1.43.108 (`eventbridgev2` client). Every claim names the test that proves it (`task test`).

## Result

- [x] **go, with two gates** — the Custom Event Bus gives the platform what ADR-001/008/011 were assembling by hand, and the Classic domain side survives unchanged:
  - **consumer-owned subscriptions with no fan-out hop**: Spike B's hand-written Classic patterns work verbatim as `DATA` filters; a consumer's queue is the subscriber's target; there is no second bus-to-bus hop to be refused.
  - **retention + replay**, **FIFO per aggregate**, **publish-time dedup** all work as documented, and replayed events are marked.
  - **a Classic domain bus can forward into the Custom central bus** (hop 1), so domains keep their bus, outbox relay and generated forward rule.
  - **loop detection is real, in one direction visible and in the other silent**: an event that came back round through a Classic bus was refused at the Custom bus with `LOOP_DETECTED` in the forward rule's DLQ; an event the Custom bus tried to send back to the Classic bus it came from was dropped with no DLQ record. Design rule: a subscriber must never target a Classic bus that forwards into the same Custom bus. Consumers subscribe straight to their own queues and functions.
- Suite: **18 passed** on the final run (`task test`), two of them recording behaviour rather than asserting the docs.
- Gates: (1) **no eu-west-2 endpoint** as of today, and (2) **no LocalStack emulation**, so L1 domain-local tests cannot cover the bus. Cross-account sharing via RAM was not exercised (one account).

## What was built (`terraform/main.tf`)

One `awscc_eventsv2_event_bus` (7-day retention). Six `awscc_eventsv2_subscriber`s, each with a delivery role, explicit retry policy and its own DLQ: two consumer subscriptions using Spike B's patterns, an everything probe with `WITH_METADATA`, a FIFO subscriber to an SQS FIFO queue keyed by `EventGroupId`, a deliberately unreachable target, and a bus-to-bus subscriber back to a Classic bus. Plus a Classic `orders-bus` with Spike B's public-forward rule targeting the Custom bus, and a probe on it. Tests create and delete two more subscribers at runtime (replay, defaults).

## Evidence

| Capability | Result | Test |
| --- | --- | --- |
| Classic event pattern (`source` prefix + `detail-type` list) as a `DATA` filter | works unchanged for `PutEvents` traffic | `test_classic_pattern_as_data_filter_reaches_consumer_subscriber` |
| `RAW` transformer (default) delivers the Classic envelope (`id`, `time`, `source`, `detail-type`, `detail`, `account`, `region`) | yes — an existing consumer needs no change | same |
| filter excludes other detail-types | yes | `test_filter_excludes_other_detail_types` |
| `WITH_METADATA` exposes `SystemMetadata`: `aws:EventId`, `aws:Source`, `aws:DetailType`, `aws:DeliveryType=LIVE`, `aws:SequenceNumber`, `aws:IngestionTime`, `EventGroupId` | yes | `test_with_metadata_transform_exposes_system_metadata` |
| no fan-out, so no echo and no own-event exclusion needed; exactly one copy per subscriber | yes | `test_no_echo_problem_without_fan_out` |
| dedup by `SystemMetadata.DeduplicationId` | second publish returns `SuccessCode=DEDUPLICATED`, one delivery | `test_dedup_by_id_suppresses_duplicate_publish` |
| content-based dedup (`DeduplicationConfiguration.DeduplicationType=CONTENT_BASED`) | same | `test_content_based_dedup_suppresses_identical_publish` |
| FIFO subscriber: 20 events in one `EventGroupId` arrive in order on an SQS FIFO queue, `MessageGroupId` from JSONata `{% $events.SystemMetadata.EventGroupId %}` | yes, 20/20 in order | `test_fifo_subscriber_preserves_order_within_event_group` |
| UNORDERED probe with the same group | delivered; order not guaranteed (recorded in test output) | `test_unordered_probe_does_not_guarantee_order` |
| `anything-but` + `prefix` accepted as a filter | yes | `test_anything_but_prefix_filter_is_accepted` |
| `wildcard` rejected at `CreateSubscriber` | yes, `InvalidInputException` naming wildcard matchers | `test_wildcard_filter_is_rejected` |
| default `RetryPolicy` | 5 attempts / 300 s — the generator must set 185 / 86400 explicitly to match Classic | `test_default_retry_policy_is_five_attempts_in_five_minutes`, `test_explicit_retry_policy_matches_classic_defaults` |
| bus `State=ACTIVE`, `RetentionPeriodInDays=7`, `RetentionWindowStartTime` reported | yes | `test_bus_retention_and_window` |
| Classic rule → Custom bus (domain keeps its bus) | delivered to the consumer subscriber | `test_classic_rule_can_target_custom_bus` |
| subscriber → Classic bus from a direct publish (one hop) | delivered | `test_subscriber_to_classic_bus_from_direct_publish_is_one_hop` |
| loop: direct publish → subscriber → Classic bus → forward rule → Custom bus | **refused at the Custom bus**: forward rule's DLQ record `ERROR_CODE=LOOP_DETECTED`, "an event can be sent to the same event bus target only once" | `task dlq-peek` after the suite |
| subscriber → Classic bus when the event *came from* that Classic bus | **silently dropped**: one copy on the Classic probe (the original put), nothing on the subscriber's DLQ within 150 s | `test_subscriber_back_to_classic_bus_from_classic_origin` (records the behaviour; fails if it changes) |
| replay: subscriber created after the fact with `StartingPosition=POINT_IN_TIME`, `PointType=TIMESTAMP` | the earlier event is re-delivered with `SystemMetadata."aws:DeliveryType"=REPLAY` and identical `Data`; subscriber reached `RUNNING` and delivered within the 180 s budget | `test_replay_via_point_in_time_subscriber_marks_events_replay` |
| unreachable target → subscriber DLQ | record arrives after the 1-attempt / 60 s policy with `ERROR_CODE=ACCESS_DENIED`, "EventBridge could not access … Check that it exists and that its policy allows the EventBridge service principal access", `EXHAUSTED_RETRY_CONDITION=MaximumRetryAttempts`, `RETRY_ATTEMPTS=1`; the failed event is inside `failedMessages` | `test_broken_target_lands_in_subscriber_dlq` |

## Recommended topology: Classic domain buses stay, central becomes Custom

This is the topology the spike tested. Each domain keeps its Classic bus for internal events, its outbox relay and the generated public-forward rule; only that rule's target changes, to the Custom central bus (one hop, proven). Each domain creates subscribers on central, from its own account, for the public events it `receives[]`, targeting its own queues and functions. Consumers never go via the domain bus.

Why not publish straight onto central and drop the domain bus: the Classic domain bus is what LocalStack can emulate, so domain-local tests keep a bus; access on a Custom bus is per bus, so internal events on a shared bus would be readable by every subscribing account; and the domain side of the catalog generator is untouched. Trade-off: internal events keep Classic semantics (no retention, no FIFO). Trigger: a domain that needs those internally gets its own Custom bus and loses LocalStack for it.

Hard rule from the loop tests: **no subscriber may target a Classic bus that forwards into the same central bus.** One direction is refused with `LOOP_DETECTED`, the other is dropped silently.

## Operational facts the generator and runbooks must respect

- **One subscriber create/delete at a time per bus.** Terraform's default parallelism hit `409 ResourceConflict ("This resource was modified concurrently")` on two of six subscribers; `-parallelism=1` fixed it. The generator's apply step must serialise subscriber changes per bus.
- **`StartingPoint` must be at least 5 minutes in the past** for a `POINT_IN_TIME` subscriber (`InvalidInputException`). Replay-after-incident is fine; "replay the last 30 seconds" is not.
- **The subscriber DLQ record is a new envelope**, not the event: `{id, version, busArn, subscriberArn, targetArn, errorCode, errorMessage, retryAttempts, exhaustedRetryCondition, failedMessages[...]}` plus SQS attributes `ERROR_CODE`, `ERROR_MESSAGE`, `EXHAUSTED_RETRY_CONDITION`, `RETRY_ATTEMPTS`, `SUBSCRIBER_ARN`, `TARGET_ARN`, `BUS_ARN`. Redrive tooling written for Classic DLQs will not parse it.
- **Validation order at `CreateSubscriber`**: the target account check runs before filter validation; a wrong-account target ARN fails with "Target resource account … must match the subscriber account", which also confirms targets must live in the subscriber's account (consumer-owned queues, as designed).
- **The bus ARN carries a generated id** (`event-busv2/<name>/<25 chars>`); subscribers and roles need the ARN, not the name. The catalog must store it per environment.
- **Pricing is per GB** ($0.18 published for the first 5,000 GB, $0.05 delivered, $0.08 per GB-month retained beyond one day) versus $1 per million Classic events. Content-based dedup is billed as a separate operation; prefer `DeduplicationId` since the outbox already has `eventId`.

## What this changes in the architecture

| ADR | Today | With the Custom Event Bus |
| --- | --- | --- |
| ADR-001 transport | domain bus → central → domain bus (refused on AWS, Spike B) | domain bus → Custom central (one Classic hop), consumers subscribe on central from their own account; no fan-out rules, no re-publisher |
| ADR-006 event shape | input transformer path unavailable | `Transformer.Type=JSONATA` per subscriber if ever needed; default `RAW` keeps the Classic envelope |
| ADR-008 replay | native archive + replay flag | bus retention + a `POINT_IN_TIME` subscriber; `aws:DeliveryType=REPLAY` replaces the `replay: true` convention |
| ADR-011 dedupe | compactor + read-time | publish-time dedup on `eventId` removes in-window duplicates; keep read-time dedupe for cross-window |
| ADR-014 region | eu-west-2 | **blocked** until London has an endpoint, or central runs in eu-west-1 with domain accounts in eu-west-2 |
| ADR-019 testing | LocalStack L1 for bus behaviour | no emulation; L1 becomes contract tests + an ephemeral sandbox stack; the retained bus itself helps (a late subscriber reads what it missed) |
| ADR-001 FIFO trigger | FIFO SQS target keyed by `aggregateId` | `Type=FIFO` subscriber with `EventGroupId=aggregateId` set by the relay |

## Reproduce

```sh
aws sso login --profile admin
task -d spikes/D-custom-event-bus apply      # ~3 min, serialised subscriber creates
task -d spikes/D-custom-event-bus test       # ~6 min; replay and DLQ tests wait
task -d spikes/D-custom-event-bus dlq-peek   # LOOP_DETECTED on the Classic forward rule's DLQ
task -d spikes/D-custom-event-bus destroy
```

## Open questions

- Cross-account: RAM sharing, subscriber ownership from a consumer account, and `aws:Source` trust across accounts need a second account.
- Throughput and event-group quotas (the quotas page did not render; check the console).
- Firehose as a subscriber target for the archive — supported per the docs, not exercised here.
- When does eu-west-2 get an endpoint, and does the hashicorp/aws provider pick it up (issue #50154)?
