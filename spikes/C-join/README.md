# Spike C — join

Only after A and B are green. Prompt: `docs/architecture/prompts/spikes/C-join-catalog-to-buses.md`.

Mechanically:
1. In Spike B's `terraform/envs/local/main.tf`, change `local.patterns` to point at
   `../../../../A-catalog-source-of-truth/generated/local/rules` and delete `spikes/B-*/patterns/`.
2. Add `task a:gen:check` to Spike B's `task test` so drift fails the run.
3. Run the behaviour-through-the-catalog tests described in the prompt and snapshot each `terraform plan`.
4. Write `findings.md` here, reconciling A and B, with the go / go-with-changes / stop recommendation.
