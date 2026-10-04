# Spikes repo — read this first

Two isolated spikes and a join, run from `docs/architecture/prompts/spikes/` (also `/arch:spike-a-*`, `/arch:spike-b-*`, `/arch:spike-c-*`).

- Spike A lives in `spikes/A-catalog-source-of-truth/` and must not touch AWS, LocalStack or Terraform.
- Spike B lives in `spikes/B-localstack-buses-end-to-end/` and must not read the catalog or any generator output.
- Spike C joins them only after both `findings.md` files say green.
- Spike D lives in `spikes/D-custom-event-bus/` and runs against a real AWS account in eu-west-1 (no LocalStack); it exists because Spike B proved Classic buses deliver one bus-to-bus hop only.

Starter code exists in both directories; keep the test names, fill in the TODOs, and write `findings.md` as you go.
Vocabulary and the decisions the spikes are testing: `docs/architecture/README.md` and `docs/architecture/decisions.md`.
Do not add AWS services or widen scope; a spike that ends with "blocked, here is why" is a valid result.
