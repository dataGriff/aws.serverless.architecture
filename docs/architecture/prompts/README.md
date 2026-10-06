# Roadmap prompts

One self-contained prompt per part of the roadmap, plus the recurring operations. Each prompt names the docs to load first, carries the hard rules, and uses the step's exit criteria as its definition of done, so an agent starting from nothing can run it.

## How to use

- Run a prompt as `/arch:<name>` (for example `/arch:step-1-walking-skeleton`), or paste the installed copy from `.claude/commands/arch/` into a fresh Claude Code session at the repo root. The installed copy is the self-contained one: the source prompt includes the shared blocks from `_partials/` by reference.
- Run the first pass in plan mode and review the task list before letting it build. One prompt per session; a step may need several sessions — the task list and the report-back carry state between them.
- Paste the prompt's **Report back** section into the PR description. Reviewers use `11-architecture-review.md`.
- If a prompt would need a service the decisions table does not permit, the agent is told to stop and run `10-evaluate-a-trigger.md`. That is the intended behaviour, not a failure.

## Prompts

| # | Roadmap part | Prompt |
| --- | --- | --- |
| 00 | day-one | [Day one · Ratify decisions, encode conventions](00-day-one-decisions-and-conventions.md) |
| 01 | day-one | [Day one · Bootstrap the EventCatalog repo](01-day-one-bootstrap-catalog.md) |
| 02 | day-one | [Day one · Terraform module library and toolchain](02-day-one-module-library-and-toolchain.md) |
| 03 | 1 | [Step 1 · Walking skeleton (single account, LocalStack)](03-step-1-walking-skeleton.md) |
| 04 | 2 | [Step 2 · The catalog generator](04-step-2-generator.md) |
| 05 | 2 | [Step 2 · CI guardrails for catalog and domain PRs](05-step-2-ci-guardrails.md) |
| 06 | 3 | [Step 3 · Payments domain, with a saga and an external webhook](06-step-3-second-domain-with-saga.md) |
| 07 | 3 | [Step 3 · platform-local, platform_testing and the erasure drill](07-step-3-isolation-tooling.md) |
| 08 | 4 | [Step 4 · Real accounts — nonprod, then prod](08-step-4-real-accounts.md) |
| 09 | 5 | [Step 5 · Reading across domains, reconciliation and the nightly guardrails](09-step-5-reads-reconciliation-guardrails.md) |
| 10 | only-when | [Only when · Evaluate whether an ADR trigger has fired](10-evaluate-a-trigger.md) |
| 11 | cross-cutting | [Cross-cutting · Review a change against the architecture](11-architecture-review.md) |
| 12 | cross-cutting | [Operation · Add or change a public event](12-add-or-change-a-public-event.md) |
| 13 | cross-cutting | [Operation · Add an API operation (command or query)](13-add-an-api-operation.md) |
| 14 | cross-cutting | [Operation · Onboard a new domain](14-onboard-a-new-domain.md) |
| 15 | cross-cutting | [Operation · Handle a subject erasure request](15-handle-an-erasure-request.md) |

## Prompt conventions

Every prompt has the same shape: **Before you start** (what to read), **Hard rules** (identical everywhere), **Goal**, **Build / Steps / Scope**, **Done when** (the exit criteria), **Report back**. The three shared blocks live once under [`_partials/`](_partials/README.md) and are inlined by `task prompts`; the **Read first** line is rendered from the prompt's frontmatter. A rule change is one edit under `_partials/` plus `task prompts`. Test names in a prompt are part of the contract: an agent that renames them has changed the acceptance criteria. When a step's roadmap entry changes, change its prompt in the same PR. `task prompts:check` fails when a prompt names a superseded ADR or uses vocabulary the spikes retired (see `install-commands.py`); the spike prompts that ran under the old ADRs are marked `historical: true` and kept as they ran.

## Spikes (before day one)

The prompts under [spikes/](spikes/README.md) drove the four spikes whose findings became ADR-021 to ADR-025; they are kept as they ran (`historical: true`). The spikes themselves, with their findings, are under [`spikes/`](../../../spikes/README.md) at the repository root.
