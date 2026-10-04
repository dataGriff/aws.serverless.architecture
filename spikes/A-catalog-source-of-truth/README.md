# Spike A — EventCatalog as the source of truth (no AWS)

Prompt: `docs/architecture/prompts/spikes/A-catalog-source-of-truth.md` (or `/arch:spike-a-catalog-source-of-truth`).

```sh
task catalog:create      # npx @eventcatalog/create-eventcatalog → ./catalog   (Node 18+)
task catalog:dev         # look at it
task gen && task checks && task spectral && task test && task gen:check
```

What's already here: `catalog-gen/catalog_gen.py` with loading, deterministic writing, `build/check/explain` and the
rule emitters sketched; `checks/` with the `x-pii` meta-schema, two real checks and four stubs; a starter Spectral
ruleset; behavioural tests that skip until `catalog/` exists. The spike fills in the emitters and stubs and keeps the
test names.

Write `findings.md` as you go; it is the deliverable.
