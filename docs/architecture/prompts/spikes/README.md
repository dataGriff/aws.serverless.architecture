# Spikes — prove the two load-bearing ideas before day one

Four spikes, all run and written up under [`spikes/`](../../../../spikes/README.md). A proved "the catalog is the source of truth" with no AWS at all; B proved that EventBridge Classic delivers one bus-to-bus hop, on LocalStack and in a real account; C replaced B's hand-written patterns with A's generated ones and showed a catalog PR changing behaviour on the buses; D proved the Custom Event Bus as central. Each was time-boxed to two days and ended in a `findings.md` that fed the ADRs and the roadmap. The prompts for A, B and C are kept as they ran (`historical: true`); D had no prompt. The code the spikes proved now lives under `platform/`, with the generator's tests.

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
