# Spikes — the evidence behind ADR-021 to ADR-025

Four time-boxed spikes, run before day one, each ending in a `findings.md` that fed back into the ADRs and the roadmap. They are kept as frozen evidence: the ADRs cite them, and nothing here is the platform. The prompts that drove them are under `docs/architecture/prompts/spikes/` (also `/arch:spike-a-*`, `/arch:spike-b-*`, `/arch:spike-c-*`).

| Spike | Question | Result | Needs |
| --- | --- | --- | --- |
| [A · catalog source of truth](A-catalog-source-of-truth/) | Can an EventCatalog repo be the single offline source from which rules, subscribers, validation bundles, Parquet schemas, PII policy and ODCS contracts are generated and checked? | go-with-changes ([findings](A-catalog-source-of-truth/findings.md)) | Node 22, uv, task. No AWS, no Docker |
| [B · LocalStack buses end to end](B-localstack-buses-end-to-end/) | Does domain bus → central → domain bus work on EventBridge Classic? | go-with-changes: one bus-to-bus hop only, proven in a real account with `THIRD_ACCOUNT_HOP_DETECTED` ([findings](B-localstack-buses-end-to-end/findings.md)) | Docker, LocalStack, Terraform |
| [C · join](C-join/) | Does a catalog edit, regenerated, change exactly the expected resources on the buses? | go-with-changes, with committed plan snapshots per edit ([findings](C-join/findings.md)) | A and B green |
| [D · Custom Event Bus](D-custom-event-bus/) | Does the EventBridge Custom Event Bus give consumer-owned subscriptions, retention, FIFO and dedup without a second hop? | go, with two gates: no eu-west-2 endpoint, no LocalStack emulation ([findings](D-custom-event-bus/findings.md)) | A real AWS account in eu-west-1, `awscc` provider |

## Rules the spikes ran under

- Spike A must not touch AWS, LocalStack or Terraform.
- While Spike B ran it read no catalog or generator output. Since Spike C (PR #4) its Terraform, Taskfile and harness read `A-catalog-source-of-truth/generated/local` and the catalog's examples on purpose; that is the join.
- Spike C has no infrastructure of its own; its scenario tests re-apply Spike B's env and own the plan snapshots.
- Spike D runs against a real account because Spike B proved Classic buses deliver one bus-to-bus hop only.
- Keep the test names (they are the acceptance criteria), fill in the TODOs, write `findings.md` as you go. A spike that ends with "blocked, here is why" is a valid result.

## Running them again

```sh
mise install && task doctor
task -d spikes/A-catalog-source-of-truth catalog:install
task -d spikes/A-catalog-source-of-truth all          # gen → check → ten checks → spectral → odcs lint → tests → site builds, tree clean
task -d spikes/C-join up                              # licensed LocalStack with ENFORCE_IAM=1; LOCALSTACK_AUTH_TOKEN from your shell
task -d spikes/C-join apply && task -d spikes/C-join test
task -d spikes/D-custom-event-bus apply test destroy  # real AWS, eu-west-1; costs money
```

Spike B's suite as it ran under ADR-001 (fan-out, the real-AWS sandbox env that produced `THIRD_ACCOUNT_HOP_DETECTED`) is at commit `eea52e9` (PR #1). What is under `B-localstack-buses-end-to-end/` now is the joined state Spike C left behind.

## What the findings changed

- A finding that contradicted an ADR went through `docs/architecture/prompts/10-evaluate-a-trigger.md`; the spike is the evidence named in the superseding ADR's frontmatter.
- A LocalStack gap became a `sandbox` marker in `docs/architecture/testing.md` and an `xfail(strict=True)` in the suite (ADR-025).
- Generator ergonomics findings changed `docs/architecture/generation-and-ci.md`, `conventions.md` and `data-contracts.md` before step 2, not during it. The full list is under "What differed from docs/architecture" in Spike A's findings.
