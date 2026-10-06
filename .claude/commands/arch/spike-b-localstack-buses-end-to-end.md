---
description: "Spike B · Domain bus ↔ central bus end to end on LocalStack (no catalog)"
---

# Spike B · Domain bus ↔ central bus end to end on LocalStack (no catalog)

> **Historical.** Ran under ADR-001 (fan-out-all) and is kept as it ran: it is the prompt that produced `THIRD_ACCOUNT_HOP_DETECTED` and ADR-021. Its `read_first` names the superseded ADRs on purpose. Read `spikes/B-localstack-buses-end-to-end/findings.md` before re-running it.

## Spike rules

- **Time-box:** two working days. If the done-when list is not green by then, stop and write up what blocked it — that is a valid result.
- **Isolation:** this spike must not depend on the other spike's output, code or decisions. Where it needs something the other spike would provide, hand-write the minimum and mark it `# SPIKE: replaced in spike C`.
- **Throwaway code, real tests:** structure can be rough; assertions cannot. Every claim in the findings must be backed by a test or a command someone else can re-run.
- **Stay inside the boundary:** build only what is listed under Build. No APIs, no encryption implementation, no compactor, no multi-account, no CI pipelines beyond local scripts, unless listed. Do not introduce any AWS service not named in the prompt.
- **Findings over polish:** finish with `findings.md` — what worked, what differed from the docs' assumptions, what the roadmap should change, open questions — and the exact commands to reproduce.
- Read `docs/architecture/README.md` for vocabulary (fan-out-all, public/internal, audience, x-pii, bronze/silver, ODCS) before starting; nothing else is required reading unless listed under **Read first**.

**Read first:** `docs/architecture/adr/ADR-001-transport-routing.md` · `docs/architecture/adr/ADR-006-event-shape.md` · `docs/architecture/testing.md`

## Question this spike answers

Do the EventBridge mechanics the design relies on — public-forward, fan-out-all with own-event exclusion, consumer rules on the domain bus, loop guard, DLQs, input transformers, envelope preservation — behave as assumed, and how faithfully does LocalStack reproduce them?

## Build (Terraform against LocalStack; patterns hand-written as JSON files so a later spike can replace them)

1. **Buses** — `central-bus`, `orders-bus`, `payments-bus` in one LocalStack account. Bus resource policies written as they would be cross-account (principal = the same account id), so the policy shape is exercised even though the boundary is not.
2. **Rules** — per domain: public-forward on the domain bus (`source` prefix own + explicit detail-type list) → central; fan-out on central (`source` anything-but own prefix) → domain bus; one consumer rule on each domain bus → an SQS probe queue. Every bus target has an IAM role and a DLQ. One forward rule carries an input transformer that drops a named field. One deliberately broken target (policy denied) to exercise the DLQ path. All patterns live in `patterns/<rule>.json` and are read by Terraform with `jsondecode(file(...))` — `# SPIKE: replaced in spike C`.
3. **Probes** — SQS queue per domain bus with a tiny poller in the test harness; optional stretch: a Lambda archiver on central writing raw events to one S3 bucket so "what flowed" can be inspected with DuckDB.
4. **Harness** — pytest + boto3 with `put(bus, source, detail_type, detail)`, `expect(queue, predicate, timeout)`, `expect_none(queue, predicate, timeout)`, `dlq_count(rule)`; a Taskfile with `up`, `apply`, `test`, `send`, `dlq`, `reset`; LocalStack compose pinned to a version.
5. **Tests** — `test_public_event_from_orders_reaches_payments_probe` · `test_internal_event_never_reaches_central_or_payments` · `test_fan_out_does_not_echo_own_event` (orders' public event never arrives back on orders' probe) · `test_three_bus_loop_terminates` (one event, counts stable after 10 s on every queue) · `test_envelope_preserved_across_two_hops` (`source`, `detail-type`, `detail`, `time` unchanged; `id` differs) · `test_input_transformer_drops_field` · `test_broken_target_lands_in_dlq` · `test_duplicate_put_is_delivered_twice` (at-least-once, documented not fixed) · `test_pattern_sizes_under_4kb` · `test_anything_but_prefix_supported_or_fallback` (if LocalStack rejects `anything-but` + `prefix`, switch the fan-out pattern to the enumerated form and record it).

## Not in scope

The catalog or any generator; APIs; Firehose; the compactor; encryption; multi-account; native archive/replay (test it only if LocalStack supports `CreateArchive`/`StartReplay`; otherwise record as sandbox-only).

## Done when

- All tests green against a fresh `task reset`; `task send -- <file>` followed by `task dlq` demonstrates the broken-target path by hand.
- `findings.md` records, with evidence: LocalStack fidelity for pattern operators (`prefix`, `anything-but`, `exists`), bus-to-bus targets with roles, DLQ delivery and its latency, input transformers, archive/replay availability; observed ordering behaviour; whether the enumerated fan-out form was needed; which of these tests must also run in a real AWS sandbox before they can be trusted.

## Report back

`findings.md` in the spike directory, plus: the commands to reproduce green, the list of things that differed from `docs/architecture/`, and a one-paragraph recommendation: proceed to day one as written, proceed with these changes, or stop.
