# Prompt partials

The three blocks every roadmap prompt shares, kept once. A prompt includes them with `{{> before-you-start}}`, `{{> hard-rules}}` and `{{> report-back}}` on a line of their own, and renders its frontmatter `read_first` list with `{{read_first}}`. `install-commands.py` inlines them when it writes `.claude/commands/arch/*.md`, so the installed command is self-contained (paste that one into a session, not the source prompt). `task prompts:check` fails when a prompt carries a literal copy of a partial instead of the include.

A rule change is an edit here followed by `task prompts`.
