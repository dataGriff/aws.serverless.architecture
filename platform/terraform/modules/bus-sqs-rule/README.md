# bus-sqs-rule

A rule on a bus whose target is an SQS queue the module creates, with a DLQ and the subscriber's retry policy. Two uses, one shape (ADR-021, ADR-025): a **consumer rule** on the domain bus for a same-domain `receives[]` (`generated/rules/{domain}-consumer-{event}.json`), and the `platform-local` rendering of a **subscriber** on the Classic stub central (`generated/subscribers/{domain}-{event}.json`: `filter` as the pattern, `retryPolicy` as the retry policy). In real accounts the subscriber is an `awscc_eventsv2_subscriber` instead; the generated file is the same.

| Input | Type | Default | Meaning |
| --- | --- | --- | --- |
| `name` | string | required | Rule and queue name |
| `bus_name` | string | required | |
| `event_pattern` | any | required | The generated pattern or subscriber filter |
| `grant_queue_access` | bool | `true` | `false` creates the deliberately unreachable target Spike B's DLQ test uses |
| `retry_policy` | object | EventBridge defaults | `{ maximumRetryAttempts, maximumEventAgeInSeconds }`; the generator sets 185 / 86 400 on every subscriber |
| `tags` | map(string) | `{}` | |

| Output | |
| --- | --- |
| `queue_url` | the target queue the tests drain |
| `dlq_url` | |
| `rule_arn` | |

The consumer's real target is its own inbox queue, created by the domain (`{service}-inbox`, the generated target reference); this module creates a queue per rule because the spike had no domain code. Step 1 wires the generated reference instead.

LocalStack: delivery and retry policy accepted; **DLQ delivery is sandbox-only on Community** (the licensed image delivers DLQ records, Spike C).
