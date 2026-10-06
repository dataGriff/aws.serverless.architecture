# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6"]
# ///
"""Render the decisions table in decisions.md from the ADR frontmatter, and lint the ADR set.

    uv run docs/architecture/adr/build-decisions.py          # rewrite the table between the markers (task adr:build)
    uv run docs/architecture/adr/build-decisions.py --check  # lint, then fail if decisions.md is not what build writes (task adr:check)

One row per accepted ADR, from its frontmatter: `concern:` (the table's Concern column), `decision:` (the Default
column, one paragraph), `revisit_when:` (the Revisit column, one sentence per entry) and `supersedes:` (rendered as
the "(supersedes ADR-nnn)" annotation). Rows keep the order of the concern they decide: a superseding ADR sits
where the ADR it replaced sat. Superseded ADRs have no row; they stay under adr/ with `superseded_by`.

The lint: every ADR has id (matching its filename), title, status in {proposed, accepted, superseded}, date and a
non-empty revisit_when; an accepted ADR has concern and decision; a superseded ADR has superseded_by naming an
existing ADR; an ADR that supersedes another is accepted and the other is superseded; an accepted ADR that
supersedes another cites evidence.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ADRS = Path(__file__).resolve().parent
DECISIONS = ADRS.parent / "decisions.md"
BEGIN, END = "<!-- BEGIN generated from adr/*.md frontmatter: task adr:build -->", "<!-- END generated -->"
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
STATUSES = {"proposed", "accepted", "superseded"}


def load() -> dict[str, dict]:
    out = {}
    for path in sorted(ADRS.glob("ADR-*.md")):
        m = FRONTMATTER.match(path.read_text())
        if not m:
            raise SystemExit(f"{path.name}: no frontmatter")
        fm = yaml.safe_load(m.group(1)) or {}
        fm["_file"] = path.name
        out[path.name[:7]] = fm
    return out


def lint(adrs: dict[str, dict]) -> list[str]:
    problems = []
    for key, fm in adrs.items():
        name = fm["_file"]
        if fm.get("id") != key:
            problems.append(f"{name}: id {fm.get('id')!r} does not match the filename")
        for field in ("title", "status", "date"):
            if not fm.get(field):
                problems.append(f"{name}: missing {field}")
        if fm.get("status") not in STATUSES:
            problems.append(f"{name}: status must be one of {sorted(STATUSES)}, not {fm.get('status')!r}")
        if not isinstance(fm.get("revisit_when"), list) or not fm["revisit_when"]:
            problems.append(f"{name}: revisit_when must be a non-empty list (the triggers that reopen it)")
        if fm.get("status") == "accepted":
            for field in ("concern", "decision"):
                if not fm.get(field):
                    problems.append(f"{name}: accepted ADRs need `{field}:` (it is the decisions.md row)")
        if fm.get("status") == "superseded":
            by = str(fm.get("superseded_by", ""))
            ref = re.match(r"(ADR-\d{3})", by)
            if not ref or ref.group(1) not in adrs:
                problems.append(f"{name}: superseded ADRs need superseded_by naming an existing ADR")
        if fm.get("supersedes"):
            old = str(fm["supersedes"])[:7]
            if fm.get("status") != "accepted" and fm.get("status") != "proposed":
                problems.append(f"{name}: supersedes {old} but is not accepted or proposed")
            if old not in adrs:
                problems.append(f"{name}: supersedes {old}, which does not exist")
            elif fm.get("status") == "accepted" and adrs[old].get("status") != "superseded":
                problems.append(f"{name}: is accepted and supersedes {old}, but {old} is not marked superseded")
            if fm.get("status") == "accepted" and not fm.get("evidence"):
                problems.append(f"{name}: an accepted ADR that supersedes another must cite evidence")
    return problems


def order_key(adrs: dict[str, dict], key: str) -> int:
    """A superseding ADR takes the slot of the one it replaced, recursively."""
    fm = adrs[key]
    old = str(fm.get("supersedes", ""))[:7]
    return order_key(adrs, old) if old in adrs else int(key[4:])


def cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def table(adrs: dict[str, dict]) -> str:
    rows = ["| ID | Concern | Default | Revisit only when |", "| --- | --- | --- | --- |"]
    accepted = sorted((k for k, fm in adrs.items() if fm.get("status") == "accepted"), key=lambda k: (order_key(adrs, k), k))
    for key in accepted:
        fm = adrs[key]
        ident = f"[{key}](adr/{fm['_file']})"
        old = str(fm.get("supersedes", ""))[:7]
        if old in adrs:
            ident += f" *(supersedes [{old}](adr/{adrs[old]['_file']}))*"
        revisit = " ".join(cell(r).rstrip(".") + "." for r in fm["revisit_when"])
        rows.append(f"| {ident} | {cell(fm['concern'])} | {cell(fm['decision'])} | {revisit} |")
    return "\n".join(rows)


def render(adrs: dict[str, dict]) -> str:
    text = DECISIONS.read_text()
    if BEGIN not in text or END not in text:
        raise SystemExit(f"{DECISIONS.name}: needs the markers {BEGIN!r} and {END!r} around the table")
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{BEGIN}\n{table(adrs)}\n{END}{tail}"


if __name__ == "__main__":
    adrs = load()
    problems = lint(adrs)
    if problems:
        raise SystemExit("ADR set is inconsistent:\n  " + "\n  ".join(problems))
    new = render(adrs)
    if "--check" in sys.argv:
        if new != DECISIONS.read_text():
            raise SystemExit("decisions.md is out of date with the ADR frontmatter — run `task adr:build` and commit")
        print(f"{len(adrs)} ADRs consistent; decisions.md matches the frontmatter")
    else:
        DECISIONS.write_text(new)
        print(f"rendered {sum(1 for fm in adrs.values() if fm.get('status') == 'accepted')} rows into {DECISIONS.name}")
