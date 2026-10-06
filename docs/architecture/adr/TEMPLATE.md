---
id: ADR-NNN
title: "Concern — the decision in a few words"
concern: "Concern"            # the Concern column of decisions.md; reuse the superseded ADR's wording when superseding
decision: >-                  # the Default column of decisions.md: one paragraph, markdown allowed, the default we build
  …
status: proposed              # proposed → accepted (or superseded, with superseded_by)
supersedes: ADR-NNN           # only when reopening a decision; delete the line otherwise
date: YYYY-MM-DD              # written
accepted: YYYY-MM-DD          # set when accepted, with the ratifiers in the CHANGELOG
evidence:                     # required when supersedes is set: the spike findings, the metric, the failed exit criterion
  - spikes/…/findings.md
revisit_when:                 # the only triggers that reopen this decision; each is one sentence "symptom → what changes"
  - "… → …"
# reviewed: unchanged | changed-after-review   # optional provenance from a critique; not read by any tool
---

# ADR-NNN · Concern — the decision in a few words

## Why ADR-NNN is reopened

*(Only when superseding.)* Which `revisit_when` trigger of the old ADR fired, or which premise failed, with the evidence named above quoted in enough detail that a reader need not open it. "It would be nicer" is not evidence (prompt 10).

## Decision

The default we build, in full. What is built, who owns it, what the generator emits for it, what a domain does and what the platform does. If a diagram shows the mechanism better than prose, put it here (Mermaid).

## What this changes

| | before (ADR-NNN) | after (this ADR) |
| --- | --- | --- |
| … | … | … |

*(Only when superseding; delete otherwise.)*

## What does not change

The buckets, contracts, conventions, tests and other ADRs this leaves alone, named explicitly, so nobody has to wonder.

## New trade-offs

What this costs, each as a consequence someone will later rediscover unless it is written here. They become lines in `trade-offs.md`.

## Implementation plan

Which roadmap step builds it, reusing which generated files and contracts. Never implement in the same PR as the ADR.

## Revisit only when

The `revisit_when` list from the frontmatter, in prose if it needs qualifying.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Set its `concern:`, `decision:` and `revisit_when` and run `task adr:build` in the same PR. Generated IaC follows the catalog, never the other way round.
