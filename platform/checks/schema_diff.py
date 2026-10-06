# /// script
# requires-python = ">=3.12"
# ///
"""Breaking-change detector for event payload schemas (dereferenced JSON Schema objects).

Breaking for consumers (tolerant readers): a property removed, a property's type changed, a property newly required,
an enum narrowed, additionalProperties tightened to false. Adding an optional property is not breaking.

    uv run checks/schema_diff.py old.json new.json      # exit 1 and list the breaking changes
"""
from __future__ import annotations
import json, sys
from pathlib import Path


def breaking_changes(old: dict, new: dict, path: str = "") -> list[str]:
    out: list[str] = []
    op, np_ = old.get("properties") or {}, new.get("properties") or {}
    for name in sorted(set(op) - set(np_)):
        out.append(f"removed property {path}{name}")
    for name in sorted(set(new.get("required") or []) - set(old.get("required") or [])):
        if name in op:
            out.append(f"{path}{name} became required")
    if old.get("additionalProperties", True) is not False and new.get("additionalProperties", True) is False:
        out.append(f"{path or '<root>'} additionalProperties tightened to false")
    for name in sorted(set(op) & set(np_)):
        o, n = op[name], np_[name]
        if o.get("type") != n.get("type"):
            out.append(f"{path}{name} type {o.get('type')} -> {n.get('type')}")
        if o.get("format") != n.get("format") and o.get("format") is not None:
            out.append(f"{path}{name} format {o.get('format')} -> {n.get('format')}")
        if "enum" in o and "enum" in n and set(o["enum"]) - set(n["enum"]):
            out.append(f"{path}{name} enum narrowed: {sorted(set(o['enum']) - set(n['enum']))}")
        if o.get("properties") or n.get("properties"):
            out.extend(breaking_changes(o, n, f"{path}{name}."))
    return out


if __name__ == "__main__":
    old, new = (json.loads(Path(p).read_text()) for p in sys.argv[1:3])
    changes = breaking_changes(old, new)
    for c in changes:
        print(f"BREAKING {c}")
    print("no breaking changes" if not changes else f"{len(changes)} breaking change(s)")
    sys.exit(1 if changes else 0)
