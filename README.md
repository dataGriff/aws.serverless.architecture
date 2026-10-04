# aws.serverless.architecture

Event & API platform on AWS serverless — proposal, decisions, and the spikes that test it.

Everything needed to run the two isolated spikes and the join, with starter code so the first session is short.

```
docs/architecture/        the proposal: decisions, ADRs, conventions, PII, data layer, contracts, testing, roadmap, prompts
.claude/commands/arch/    the prompts as Claude Code commands  (/arch:spike-a-catalog-source-of-truth …)
spikes/A-…                catalog + generator skeleton + checks + tests   (no AWS)
spikes/B-…                LocalStack: 3 buses, hand-written patterns, probes, DLQ, harness, 10 tests
spikes/C-join/            how to join A and B once both are green
```

## Quick start (about 30 minutes before the agents take over)

1. Prerequisites: Docker running, `mise` installed. Then `mise install && task doctor`.
2. Spike B needs nothing else: `cd spikes/B-localstack-buses-end-to-end && task up && task apply && task test`
   — expect some tests to fail on a fresh LocalStack; the spike's job is to find out which and why.
3. Spike A needs the catalog created once: `cd spikes/A-catalog-source-of-truth && task catalog:create`
   (interactive, pick the default template), then `task all`. Tests skip until `catalog/` exists.
4. Open two Claude Code sessions (worktrees work well): run `/arch:spike-a-catalog-source-of-truth` in one and
   `/arch:spike-b-localstack-buses-end-to-end` in the other, in plan mode first. Approve the task lists, let them run,
   review `findings.md` as it fills in.
5. When both findings say green, one more session: `/arch:spike-c-join-catalog-to-buses`.

## Things to decide before you start (two minutes each)

- EventCatalog version to pin (A) and LocalStack image tag to pin (B). Write both into `findings.md` headers.
- Whether the input-transformer-on-bus-target question (ADR-006) is answered in B with LocalStack only, or also
  against a real sandbox. LocalStack passing is not proof; the prompt says so.

## What "done" looks like

Three `findings.md` files, a recommendation (go / go-with-changes / stop), and a list of ADR triggers or roadmap
edits with the spike as evidence. Nothing from the spikes is kept except tests that still describe desired behaviour.
