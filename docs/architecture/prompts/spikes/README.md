# Spikes — prove the two load-bearing ideas before day one

Two isolated spikes and one join. A proves "the catalog is the source of truth" with no AWS at all; B proves "domain bus to central bus and back" on LocalStack with no catalog at all; C replaces B's hand-written patterns with A's generated ones and shows a catalog PR changing behaviour on the buses. Each is time-boxed to two days and ends in a `findings.md` that feeds back into the ADRs and the roadmap.

Suggested layout: `spikes/A-catalog-source-of-truth/`, `spikes/B-localstack-buses-end-to-end/`, `spikes/C-join/` — separate directories, separate sessions, no shared code until C.

| Spike | Prompt | Needs | Command |
| --- | --- | --- | --- |
| A | [Spike A · EventCatalog as the source of truth (no AWS)](A-catalog-source-of-truth.md) | Node, Python/uv | `/arch:spike-a-catalog-source-of-truth` |
| B | [Spike B · Domain bus ↔ central bus end to end on LocalStack (no catalog)](B-localstack-buses-end-to-end.md) | Docker, LocalStack, Terraform | `/arch:spike-b-localstack-buses-end-to-end` |
| C | [Spike C · Join — generated patterns drive the LocalStack buses](C-join-catalog-to-buses.md) | A and B green | `/arch:spike-c-join-catalog-to-buses` |
| D | Spike D · EventBridge Custom Event Bus as the central bus (added after B found the Classic one-hop limit; no prompt file — see `spikes/D-custom-event-bus/README.md`) | real AWS account, eu-west-1, `awscc` provider | `task -d spikes/D-custom-event-bus apply test destroy` |

## What to do with the findings

- A finding that contradicts an ADR goes through `prompts/10-evaluate-a-trigger.md` — the spike is the evidence.
- A LocalStack gap becomes a `sandbox-only` marker in `testing.md` and a line in the module READMEs.
- A generator ergonomics finding changes `generation-and-ci.md` before step 2 starts, not during it.
- If C recommends stop, the write-up is the deliverable; nothing from the spikes is kept except the tests that still describe desired behaviour.
