---
step: only-when
when: >-
  Use whenever someone asks for a service or change the decisions table does not permit (Athena, Glue, Iceberg, Kinesis, Temporal, Step Functions outside the saga, CloudFront, a Schema Registry, a data platform account, a second region, a different bus topology): decide with evidence whether an ADR's revisit_when trigger has fired and either propose a superseding ADR or name the alternative inside current defaults. Triggers on 'can we use', 'why can't we', 'should we add', 'is the trigger fired', 'new ADR'.
title: "Only when · Evaluate whether an ADR trigger has fired"
read_first:
  - docs/architecture/decisions.md
  - the relevant docs/architecture/adr/ADR-*.md
  - docs/architecture/trade-offs.md
---

# Only when · Evaluate whether an ADR trigger has fired

{{> before-you-start}}

{{> hard-rules}}

**Read first:** {{read_first}}

## Goal

Decide, with evidence, whether a request or symptom is one of the named triggers that reopens a decision — and if it is not, say what the current defaults already offer.

## Procedure

1. Restate the request or symptom in one sentence. Identify the ADR(s) it touches.
2. Quote the ADR's `revisit_when` entries. For each, state whether it has fired and the evidence: metrics, costs, a failed exit criterion, a regulatory requirement, a measured limit. "It would be nicer" is not evidence.
3. If none has fired: answer with the cheapest way to meet the need inside current defaults (a read model, a FIFO target, a transformer, a reader role, a contract overlay), and stop.
4. If one has fired: write `adr/ADR-NNN-<slug>.md` with `status: proposed`, `supersedes: ADR-xxx`, the evidence, what changes, what explicitly does not change (buckets, contracts, conventions, tests), the new trade-offs, and an implementation plan that reuses the same generated files and contracts. Give it `concern:` and `decision:` in its frontmatter and its own `revisit_when`, then `task adr:build` renders its row into `decisions.md` in the same PR (`task adr:check` must pass).
5. Never implement the change in the same PR as the ADR.

## Output

Either "no trigger fired — do this instead" with the alternative, or the proposed ADR and a plan. Nothing in between.

{{> report-back}}
