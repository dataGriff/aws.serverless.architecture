# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6"]
# ///
"""Check that platform.yaml has been localised and that no placeholder is left in the tree.

    uv run scripts/localise_check.py            # fails on the first unlocalised parameter or leftover placeholder
    uv run scripts/localise_check.py --report   # prints every parameter's state and occurrences, never fails

A parameter is localised when its `value` differs from its `placeholder` (or, for `required` parameters that
have no placeholder text, when `value` is non-empty). Once localised, its placeholder must be gone from every
scanned file. History is never scanned: findings, ADRs, golden snapshots, fixtures.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "platform.yaml"

NEVER_SCAN = ("/.git/", "/node_modules/", "/tests/golden/", "/fixtures/", "/.terraform/", "/dist/",
              "/.eventcatalog-core/", "/generated/", "/.scenarios/")
NEVER_SCAN_NAMES = {"findings.md", "package-lock.json", "platform.yaml", "CHANGELOG.md"}
NEVER_SCAN_DIRS = ("docs/architecture/adr/",)
TEXT_SUFFIXES = {".md", ".mdx", ".yml", ".yaml", ".json", ".js", ".ts", ".py", ".tf", ".html", ".txt", ".toml", ".cfg", ".ini", ""}


def scannable(path: Path, extra_excludes: list[str]) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    if path.name in NEVER_SCAN_NAMES or path.suffix not in TEXT_SUFFIXES:
        return False
    if any(seg in f"/{rel}/" for seg in NEVER_SCAN) or rel.startswith(NEVER_SCAN_DIRS):
        return False
    return not any(rel.startswith(x) for x in extra_excludes)


def occurrences(token: str, extra_excludes: list[str]) -> list[str]:
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or not scannable(path, extra_excludes):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        hits += [f"{path.relative_to(ROOT).as_posix()}:{n}" for n, line in enumerate(lines, 1) if token in line]
    return hits


def main(report: bool) -> int:
    params = yaml.safe_load(CONFIG.read_text())["parameters"]
    failures = 0
    for name, p in params.items():
        placeholder, value = p.get("placeholder"), p.get("value") or ""
        excludes = p.get("exclude", [])
        if placeholder is None:
            state = "set" if value else "MISSING (required)" if p.get("required") else "optional, unset"
            bad = p.get("required") and not value
            detail = ""
        elif value == placeholder:
            state, bad = "NOT LOCALISED", True
            detail = f" ({len(occurrences(placeholder, excludes))} occurrences to replace)" if report else ""
        else:
            left = occurrences(placeholder, excludes)
            state, bad = ("LEFTOVER placeholder", True) if left else ("localised", False)
            detail = ("\n    " + "\n    ".join(left)) if left else ""
        failures += bool(bad)
        if report or bad:
            print(f"{name:26} {state}{detail}")
        if bad and not report:
            break
    if report:
        print(f"\n{len(params) - failures}/{len(params)} parameters localised")
        return 0
    if failures:
        print("\nplatform.yaml is not localised yet; fill in `value` and replace the placeholder, or run with --report")
        return 1
    print(f"platform.yaml: all {len(params)} parameters localised, no placeholders left")
    return 0


if __name__ == "__main__":
    sys.exit(main("--report" in sys.argv))
