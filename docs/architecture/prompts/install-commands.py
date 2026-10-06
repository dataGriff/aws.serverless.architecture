"""Install docs/architecture/prompts/*.md as Claude Code commands under .claude/commands/arch/.

The prompt file is the source. The command is the same body with a one-line frontmatter
(`description: <title>`), named after the prompt without its numeric prefix, with the shared blocks under
`_partials/` inlined where the prompt says `{{> name}}` and the frontmatter `read_first` list rendered where it
says `{{read_first}}`, so the installed command is self-contained. Run: task prompts

`--check` also lints the prompts against the ADR set and the conventions the spikes settled, so a
prompt cannot drift behind the docs again:
  - no prompt names an ADR whose frontmatter says `status: superseded`
  - no prompt carries a literal copy of a partial instead of its `{{> name}}` include
  - no prompt uses vocabulary EventCatalog rejects or the spikes retired (`openapiPath`, a bare
    `visibility:`/`audience:` key, a `sunset` field, `versioned/1/` as the current version)
A prompt with `historical: true` in its frontmatter (the spike prompts that ran under the old ADRs)
is installed but not linted.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROMPTS = ROOT / "docs" / "architecture" / "prompts"
COMMANDS = ROOT / ".claude" / "commands" / "arch"
ADRS = ROOT / "docs" / "architecture" / "adr"
PARTIALS = PROMPTS / "_partials"

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
TITLE = re.compile(r'^title:\s*"?(.*?)"?\s*$', re.M)
STATUS = re.compile(r"^status:\s*(\S+)", re.M)
ADR_REF = re.compile(r"\bADR-(\d{3})\b")
INCLUDE = re.compile(r"^\{\{> ([a-z0-9-]+)\}\}$", re.M)
READ_FIRST = re.compile(r"^read_first:\n((?:  - .*\n)+)", re.M)

# (regex, why it is wrong, what to write instead) — see conventions.md and spikes/A-catalog-source-of-truth/findings.md
RETIRED = [
    (re.compile(r"openapiPath"), "legacy EventCatalog form", "specifications: [{type: openapi, path, name}]"),
    (re.compile(r"`visibility(: [a-z]+)?`"), "EventCatalog fails the build on bare platform keys", "`x-visibility`"),
    (re.compile(r"`audience(: [a-z]+)?`"), "EventCatalog fails the build on bare platform keys", "`x-audience`"),
    (re.compile(r"`sunset`"), "EventCatalog has no sunset field", "`deprecated.date` (the HTTP `Sunset` header on APIs is fine)"),
    (re.compile(r"versioned/1/"), "versioned/<v>/ holds previous versions", "the current version at events/<Event>/"),
]


def split(prompt: Path) -> tuple[str, str]:
    text = prompt.read_text()
    m = FRONTMATTER.match(text)
    if not m:
        raise SystemExit(f"{prompt}: no frontmatter")
    return m.group(1), text[m.end():]


def render(fm: str, body: str, prompt: Path) -> str:
    """Inline `{{> name}}` from _partials/<name>.md and render `{{read_first}}` from the frontmatter list."""
    def partial(m: re.Match) -> str:
        f = PARTIALS / f"{m.group(1)}.md"
        if not f.exists():
            raise SystemExit(f"{prompt}: unknown partial {{{{> {m.group(1)}}}}} (no {f.relative_to(ROOT)})")
        return f.read_text().rstrip("\n")
    body = INCLUDE.sub(partial, body)
    if "{{read_first}}" in body:
        m = READ_FIRST.search(fm + "\n")
        if not m:
            raise SystemExit(f"{prompt}: uses {{{{read_first}}}} but has no read_first list in its frontmatter")
        items = [line.strip()[2:].strip() for line in m.group(1).splitlines()]
        body = body.replace("{{read_first}}", " · ".join(f"`{i}`" for i in items))
    return body


def install(prompt: Path) -> Path:
    fm, body = split(prompt)
    title = TITLE.search(fm)
    if not title:
        raise SystemExit(f"{prompt}: no title")
    body = render(fm, body, prompt)
    rel = prompt.relative_to(PROMPTS).as_posix()
    slug = re.sub(r"^\d+-", "", rel.rsplit("/", 1)[-1]).removesuffix(".md")
    if rel.startswith("spikes/"):  # A-catalog-source-of-truth.md -> spike-a-catalog-source-of-truth
        slug = "spike-" + slug[0].lower() + slug[1:]
    out = COMMANDS / f"{slug}.md"
    out.write_text(f'---\ndescription: "{title.group(1)}"\n---\n{body}')
    return out


def superseded_adrs() -> dict[str, str]:
    out = {}
    for adr in sorted(ADRS.glob("ADR-*.md")):
        fm = FRONTMATTER.match(adr.read_text())
        status = STATUS.search(fm.group(1)) if fm else None
        if status and status.group(1) == "superseded":
            out[adr.name[:7]] = adr.name
    return out


def lint(prompt: Path, superseded: dict[str, str]) -> list[str]:
    fm, body = split(prompt)
    if re.search(r"^historical:\s*true", fm, re.M):
        return []
    rel = prompt.relative_to(ROOT).as_posix()
    problems = []
    for f in sorted(PARTIALS.glob("*.md")):
        if f.name == "README.md":
            continue
        marker = f.read_text().splitlines()[2]   # the first body line after the heading and its blank line
        if marker and marker in body:
            problems.append(f"{rel}: carries a literal copy of _partials/{f.name}; use {{{{> {f.stem}}}}} instead")
    for n, line in enumerate(prompt.read_text().splitlines(), 1):
        for m in ADR_REF.finditer(line):
            ref = f"ADR-{m.group(1)}"
            if ref in superseded:
                problems.append(f"{rel}:{n}: names {ref}, which is superseded ({superseded[ref]}); cite its successor")
        for rx, why, instead in RETIRED:
            if rx.search(line):
                problems.append(f"{rel}:{n}: `{rx.search(line).group(0)}` — {why}; write {instead}")
    return problems


if __name__ == "__main__":
    COMMANDS.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in PROMPTS.rglob("*.md") if p.name != "README.md" and PARTIALS not in p.parents)
    written = [install(p) for p in files]
    print(f"installed {len(written)} commands into {COMMANDS.relative_to(ROOT)}")
    if "--check" in sys.argv:
        import subprocess
        superseded = superseded_adrs()
        problems = [p for f in files for p in lint(f, superseded)]
        if problems:
            raise SystemExit("prompts drifted behind the docs:\n  " + "\n  ".join(problems))
        print(f"linted {len(files)} prompts against {len(superseded)} superseded ADRs: clean")
        if subprocess.run(["git", "diff", "--quiet", "--", str(COMMANDS)], cwd=ROOT).returncode:
            raise SystemExit("commands out of date with prompts — run `task prompts` and commit")
