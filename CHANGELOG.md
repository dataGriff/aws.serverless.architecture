# Changelog

The history of this repository's decisions and structure. An adopter's fork starts its own list here; the entries below are this repository's provenance and are not part of the pattern.

## Unreleased

- Adoption path: README rewritten for an adopter, MIT licence, limits and cost of entry on the first screen; the spike quick start moved to `spikes/README.md` (#7).
- Roadmap prompts brought in line with the spike findings; `task prompts:check` fails on a superseded ADR or retired vocabulary (#9).
- `platform.yaml` names every placeholder; `task localise:check` is prompt 00's exit gate; `orders`/`payments` marked as the worked example (#8).
- The generator, checks, Terraform modules and harness moved from the spikes to `platform/`; `templates/catalog-repo` and `templates/domain-repo` added (#10).
- `AGENTS.md` and `CLAUDE.md` as the agent entry point; prompts installed as skills; committed permissions (#11).
- The prompts' shared blocks live once under `_partials/` (#12).
- `decisions.md` rendered from the ADR frontmatter; `task adr:check` lints the ADR set (#13).
- `adr/TEMPLATE.md` and this changelog; the dated rules of engagement moved here from `decisions.md` (#15).
- Root CI workflow on pull requests (prompts, ADRs, links, Spike A's pipeline, the templates); `overview.html` published with the catalog site (#14).
- Agents query the catalog through its MCP server (Scale licence) or the published `llms.txt`; `.mcp.json.example` (#16).

## 2026-10-05

- PR #5: `docs/architecture/overview.html`, a shareable one-page reference with the diagrams.
- PR #4 (Spike C): Spike A's generated output drives Spike B's LocalStack buses with no hand-written pattern left; plan snapshots per catalog edit; the generator drops fan-out and emits a consumer-owned target reference per subscriber; `causationId` decided as absent, never null.

## 2026-10-04

- Initial proposal: the architecture docs, ADR-001 to ADR-020, the roadmap prompts and the spike starters.
- Architecture critique: fourteen ADRs changed after review (`reviewed: changed-after-review` in their frontmatter); their previous defaults are not to be reintroduced without a new ADR.
- Spike A (PR #2): EventCatalog as the source of truth, no AWS. Go-with-changes; the conventions it settled (`x-` prefixed frontmatter keys, per-event logical channels, `$id` references, the build-idempotency gate, generated command/query pages) folded into `conventions.md`, `data-contracts.md` and `generation-and-ci.md`.
- Spike B (PR #1): bus-to-bus mechanics on LocalStack and in a real account. EventBridge Classic delivers one bus-to-bus hop; ADR-001's fan-out-all refused with `THIRD_ACCOUNT_HOP_DETECTED`. Input transformers rejected on bus targets.
- Spike D: the EventBridge Custom Event Bus as central. Go with two gates (no eu-west-2 endpoint, no LocalStack emulation); `LOOP_DETECTED` in one direction, a silent drop in the other.
- ADR-021 to ADR-025 proposed from Spikes B and D, then accepted (PR #3) on the evidence in `spikes/*/findings.md`, superseding ADR-001, 006, 008, 009 and 019. Two decisions taken at acceptance: the platform region is eu-west-1 (no London endpoint for the Custom Event Bus) and domain-local tests use licensed LocalStack with `ENFORCE_IAM=1`. Ratified by the repository owner.
- Pages workflow publishes the Spike A catalog from main.
