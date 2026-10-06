---
historical: true
title: "Spike A · EventCatalog as the source of truth (no AWS)"
read_first:
  - docs/architecture/conventions.md
  - docs/architecture/pii.md
  - docs/architecture/data-contracts.md
  - docs/architecture/generation-and-ci.md
---

# Spike A · EventCatalog as the source of truth (no AWS)

> **Historical.** Ran before ADR-021 to ADR-025 were accepted and is kept as it ran; its vocabulary (`visibility`, fan-out patterns, bus channel pages) is superseded by `conventions.md` and by what `spikes/A-catalog-source-of-truth/findings.md` found. Read the findings before re-running it.

## Spike rules

- **Time-box:** two working days. If the done-when list is not green by then, stop and write up what blocked it — that is a valid result.
- **Isolation:** this spike must not depend on the other spike's output, code or decisions. Where it needs something the other spike would provide, hand-write the minimum and mark it `# SPIKE: replaced in spike C`.
- **Throwaway code, real tests:** structure can be rough; assertions cannot. Every claim in the findings must be backed by a test or a command someone else can re-run.
- **Stay inside the boundary:** build only what is listed under Build. No APIs, no encryption implementation, no compactor, no multi-account, no CI pipelines beyond local scripts, unless listed. Do not introduce any AWS service not named in the prompt.
- **Findings over polish:** finish with `findings.md` — what worked, what differed from the docs' assumptions, what the roadmap should change, open questions — and the exact commands to reproduce.
- Read `docs/architecture/README.md` for vocabulary (fan-out-all, public/internal, audience, x-pii, bronze/silver, ODCS) before starting; nothing else is required reading unless listed under **Read first**.

**Read first:** `docs/architecture/conventions.md` · `docs/architecture/pii.md` · `docs/architecture/data-contracts.md` · `docs/architecture/generation-and-ci.md`

## Question this spike answers

Can an EventCatalog repository be the single source from which routing patterns, schemas, PII policy and data contracts are *generated and checked*, entirely offline — such that a PR to the catalog is the only way any of those change?

## Build (all local; Node for the catalog, Python/uv for the generator; no AWS, no LocalStack, no Terraform)

1. **Catalog** — two domains (`orders`, `payments`), one service each. Events: `OrderPlaced.v1` (public; `customerId` `x-pii: indirect`, `customerEmail` `x-pii: direct` with `encryption: subject-key` and `decryptors: [payments]`, `total` Money), `order.aggregate.updated` (internal), `PaymentCaptured.v1` (public). `receives[]` both ways. One OpenAPI for `order-service` with `POST /v1/orders` (`x-eventcatalog-message-type: command`) and `GET /v1/orders/{id}` (`query`). `schemas/` with `Money` and `Address` at the root and `schemas/orders/Order`. Channels for `central-bus`, both domain buses and the orders API. Two example payloads per event. A `data-product.yaml` overlay for each public event. CODEOWNERS per domain path.
2. **`catalog-gen`** — a deterministic CLI with these emitters only, writing JSON/YAML under `generated/local/`: per-domain public-forward pattern (detail-type list from `visibility`); per-domain fan-out pattern (`source` anything-but own prefix) *and* the alternative enumerated form (list of the other domains' prefixes) side by side; consumer rule patterns from `receives[]`; archive routing map (source prefix → bucket name); validation schema bundle per domain (event schemas + the list of `direct` fields that must be ciphertext); Parquet schema per public event (`d_*` only for `none`/`indirect`); ODCS v3 contract per public event merged with its overlay; deploy-order manifest. Include `catalog-gen check` (fails on drift) and `catalog-gen explain <generated-file>`.
3. **Checks** — local scripts (and a workflow file, unexecuted is fine): `x-pii` on every field via a meta-schema; `special` forbidden; `direct` on a public event requires `encryption` + `decryptors`; every `receives[]` targets a public or same-domain event; `source` namespace matches the owning domain; every `$ref` resolves into `schemas/` with no entity at the root; Spectral on the OpenAPI with the conventions encoded; ODCS lint; schema diff between `OrderPlaced` v1 and a fixture v2 that removes a field; sync-hop-depth over the catalog graph.
4. **Tests** — golden snapshots of `generated/local/`; a test that flips `order.aggregate.updated` to public and asserts the exact set of files that change (forward pattern, routing map, Parquet schema, ODCS, manifest, nothing else); a test that adds a `receives[]` and asserts only the consumer pattern and manifest change; a test that each check fails on its own fixture and passes on the clean catalog.
5. **Site** — `npm run build` renders; the event page shows the schema, the API operations are visible as commands/queries, the ODCS file is reachable from the event page in whatever way the installed version supports.

## Not in scope

Applying anything to AWS or LocalStack; encrypting anything; the compactor; real CI runners; APIs beyond the spec; more than two domains.

## Done when

- `catalog-gen build` is deterministic across two runs and `catalog-gen check` fails after a one-character edit to any generated file.
- The flip-visibility and add-subscription tests assert exact file sets and pass.
- Every check has a failing fixture and a clean pass; the catalog site builds.
- The generated fan-out pattern and its enumerated alternative are both under 4 KB for a fixture with twelve public events, or the generator splits them and a test proves it.
- `findings.md` records: which EventCatalog features the installed version actually renders (specifications, attachments, anything resembling data products or containers); how the overlay merge should behave on conflicts; whether `x-pii` belongs in JSON Schema or in catalog frontmatter; anything in `generation-and-ci.md` that proved awkward.

## Report back

`findings.md` in the spike directory, plus: the commands to reproduce green, the list of things that differed from `docs/architecture/`, and a one-paragraph recommendation: proceed to day one as written, proceed with these changes, or stop.
