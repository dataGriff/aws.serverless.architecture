---
title: "Spike C · Join — generated patterns drive the LocalStack buses"
read_first:
  - spikes/A-catalog-source-of-truth/findings.md
  - spikes/B-localstack-buses-end-to-end/findings.md
  - docs/architecture/generation-and-ci.md
---

# Spike C · Join — generated patterns drive the LocalStack buses

## Spike rules

- **Time-box:** two working days. If the done-when list is not green by then, stop and write up what blocked it — that is a valid result.
- **Isolation:** this spike must not depend on the other spike's output, code or decisions. Where it needs something the other spike would provide, hand-write the minimum and mark it `# SPIKE: replaced in spike C`.
- **Throwaway code, real tests:** structure can be rough; assertions cannot. Every claim in the findings must be backed by a test or a command someone else can re-run.
- **Stay inside the boundary:** build only what is listed under Build. No APIs, no encryption implementation, no compactor, no multi-account, no CI pipelines beyond local scripts, unless listed. Do not introduce any AWS service not named in the prompt.
- **Findings over polish:** finish with `findings.md` — what worked, what differed from the docs' assumptions, what the roadmap should change, open questions — and the exact commands to reproduce.
- Read `docs/architecture/README.md` for vocabulary (fan-out-all, public/internal, audience, x-pii, bronze/silver, ODCS) before starting; nothing else is required reading unless listed under **Read first**.

**Read first:** `spikes/A-catalog-source-of-truth/findings.md` · `spikes/B-localstack-buses-end-to-end/findings.md` · `docs/architecture/generation-and-ci.md`

## Question this spike answers

When Spike A's generated output replaces Spike B's hand-written patterns, does a catalog PR become the only thing that changes behaviour on the buses — and do the two spikes' findings agree?

## Preconditions

Both spikes green, both `findings.md` written. Do not start otherwise.

## Build

1. Point Spike B's Terraform at `generated/local/` from Spike A: forward, fan-out and consumer patterns, the bus policy principal lists, and the routing map for the optional archiver. Delete every file marked `# SPIKE: replaced in spike C`. If Spike B found `anything-but` + `prefix` unsupported, select the enumerated fan-out form via a generator flag, not a hand edit.
2. Wire `catalog-gen check` into `task test` so drift fails the run.
3. Behaviour-through-the-catalog tests: flip `order.aggregate.updated` to public in the catalog → regenerate → `terraform plan` shows exactly the forward pattern (and routing map) changing → apply → the event now reaches the payments probe; revert and prove it stops. Add `receives[]` on payments for a second event → only the consumer pattern changes → the probe receives it. Remove a `receives[]` → delivery stops.
4. If Spike B built the archiver: load the generated validation bundle into it; a payload that violates its schema, or a `direct` field in clear, is written under `processing-failed/` instead of the normal prefix; a DuckDB query over the bucket shows both prefixes.
5. Record the plan diffs as snapshot files so the "exact set of changes" claim is reviewable.

## Not in scope

Anything the two spikes excluded. In particular no APIs, no encryption, no compactor, no CI runners.

## Done when

- No hand-written pattern or policy remains; `grep -r SPIKE` finds nothing.
- Each behaviour-through-the-catalog test passes and its plan snapshot shows only the expected files changing.
- `findings.md` reconciles A and B: assumptions both spikes made that turned out different; the list of changes to `roadmap.md`, `generation-and-ci.md` and the ADRs; a go / go-with-changes / stop recommendation for day one.

## Report back

`findings.md` in the spike directory, plus: the commands to reproduce green, the list of things that differed from `docs/architecture/`, and a one-paragraph recommendation: proceed to day one as written, proceed with these changes, or stop.
