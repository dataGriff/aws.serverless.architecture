# Platform catalog

A PR here is how you publish an event, subscribe to one, or expose an API.

Everything in every AWS account is generated from this catalog (ADR-017): forward rules, subscribers, the archive's validation bundles, Parquet schemas, ODCS data contracts, API bodies, clients, alarms and reader roles. Nothing is changed by hand in an account; you change the catalog and the generator does the rest.

- `domains/<domain>/` owns `services/`, `events/`, `commands/`, `queries/`, its `schemas/<domain>/` entities and its data products. `CODEOWNERS` enforces it.
- Every JSON Schema property carries `x-pii` (`none` · `indirect` · `direct` · `special`). `direct` on a public event needs `encryption: subject-key` and `decryptors`; `special` never enters an event.
- Event frontmatter: `x-visibility: public|internal`, `x-audience: all|restricted`, `x-source: {domain}.{service}`. Platform keys are `x-` prefixed; the build rejects unknown bare keys.
- A service `sends[].to` its own bus's channel for the event (`{domain}-bus.{detail-type}`) and `receives[].from` its own subscriber channel (`{domain}-sub.{detail-type}`). Those channel pages are generated; the only hand-written channels are APIs.
- Shared `schemas/*.json` are value objects owned by the platform team; entities live under `schemas/<domain>/`. Event schemas reference shared schemas by `$id` URL.
- The current event version lives at `events/<Event>/`; previous versions under `events/<Event>/versioned/<v>/`.
- Hand-written `commands/` and `queries/` pages mirror each OpenAPI operation (`id` = `operationId`) until the generator emits them.

`sample` is the starter domain: rename it to your first real domain (or delete it once you have one). The conventions it demonstrates are in `docs/architecture/conventions.md` of the platform repo.

```sh
task catalog:install   # npm ci
task all               # gen → gen:check → checks → spectral → odcs:lint → catalog:build:clean
task catalog:dev       # http://localhost:3000
```
