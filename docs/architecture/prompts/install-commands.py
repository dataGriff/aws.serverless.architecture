"""Install docs/architecture/prompts/*.md as Claude Code commands under .claude/commands/arch/.

The prompt file is the source. The command is the same body with a one-line frontmatter
(`description: <title>`), named after the prompt without its numeric prefix. Run: task prompts
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROMPTS = ROOT / "docs" / "architecture" / "prompts"
COMMANDS = ROOT / ".claude" / "commands" / "arch"

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
TITLE = re.compile(r'^title:\s*"?(.*?)"?\s*$', re.M)

def install(prompt: Path) -> Path:
    text = prompt.read_text()
    m = FRONTMATTER.match(text)
    if not m:
        raise SystemExit(f"{prompt}: no frontmatter")
    title = TITLE.search(m.group(1))
    if not title:
        raise SystemExit(f"{prompt}: no title")
    body = text[m.end():]
    rel = prompt.relative_to(PROMPTS).as_posix()
    slug = re.sub(r"^\d+-", "", rel.rsplit("/", 1)[-1]).removesuffix(".md")
    if rel.startswith("spikes/"):  # A-catalog-source-of-truth.md -> spike-a-catalog-source-of-truth
        slug = "spike-" + slug[0].lower() + slug[1:]
    out = COMMANDS / f"{slug}.md"
    out.write_text(f'---\ndescription: "{title.group(1)}"\n---\n{body}')
    return out


if __name__ == "__main__":
    COMMANDS.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in PROMPTS.rglob("*.md") if p.name != "README.md")
    written = [install(p) for p in files]
    print(f"installed {len(written)} commands into {COMMANDS.relative_to(ROOT)}")
    if "--check" in sys.argv:
        import subprocess
        if subprocess.run(["git", "diff", "--quiet", "--", str(COMMANDS)], cwd=ROOT).returncode:
            raise SystemExit("commands out of date with prompts — run `task prompts` and commit")
