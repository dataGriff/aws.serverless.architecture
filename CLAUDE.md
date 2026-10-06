@AGENTS.md

## Claude Code specifics

- The prompts are installed as `/arch:<name>` commands (`.claude/commands/arch/`) and as skills (`.claude/skills/arch-<name>/`), both generated from `docs/architecture/prompts/` by `task prompts`. Edit the prompt, never the installed copy.
- Run a roadmap prompt in plan mode first and get the task list approved before building. One prompt per session.
- `.claude/settings.json` pre-allows `task`, `uv`, `npx`, `npm run`, `terraform plan`/`validate`, `docker compose` and `aws` against LocalStack, and denies `terraform apply`/`destroy`; do not widen it.
- Finish a prompt with its **Report back** section; it goes in the PR description.
