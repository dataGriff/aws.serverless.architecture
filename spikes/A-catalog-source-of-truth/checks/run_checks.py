# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6", "python-frontmatter>=1.1", "jsonschema>=4"]
# ///
"""Spike A checks. Each check prints `OK <name>` or `FAIL <name>: <why> (see docs/architecture/<file>)` and the
process exits non-zero if anything failed. Add checks as functions returning a list of failure strings.

    uv run checks/run_checks.py --catalog catalog
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import frontmatter, jsonschema

HERE = Path(__file__).parent
META = json.loads((HERE / "x-pii.metaschema.json").read_text())


def event_schemas(cat: Path):
    for p in sorted(cat.glob("events/**/schema.json")):
        yield p, json.loads(p.read_text())


def check_x_pii(cat: Path) -> list[str]:
    fails = []
    for p, schema in event_schemas(cat):
        try:
            jsonschema.validate(schema, META)
        except jsonschema.ValidationError as e:
            fails.append(f"{p}: {e.message} (pii.md)")
    return fails


def check_direct_on_public_requires_encryption(cat: Path) -> list[str]:
    fails = []
    for md in sorted(cat.glob("events/**/index.md*")):
        fm = frontmatter.load(md)
        schema_p = md.parent / "schema.json"
        if fm.get("visibility") != "public" or not schema_p.exists():
            continue
        for name, prop in json.loads(schema_p.read_text()).get("properties", {}).items():
            if prop.get("x-pii") == "direct" and (prop.get("encryption") != "subject-key" or not prop.get("decryptors")):
                fails.append(f"{md.parent.name}.{name}: direct PII on a public event needs encryption: subject-key and decryptors (pii.md)")
    return fails


def check_receives_target_public_or_same_domain(cat: Path) -> list[str]:
    # TODO: load services + events; fail when a service receives an internal event from another domain (generation-and-ci.md)
    return []


def check_source_namespace(cat: Path) -> list[str]:
    # TODO: every event's source prefix equals its owning domain (conventions.md)
    return []


def check_refs_into_schemas(cat: Path) -> list[str]:
    # TODO: every $ref resolves under schemas/; no entity at schemas/ root (conventions.md)
    return []


def check_sync_hop_depth(cat: Path) -> list[str]:
    # TODO: build the command/query call graph from services' sends/receives; fail on depth > 1 (decisions.md: Sync vs async)
    return []


CHECKS = [check_x_pii, check_direct_on_public_requires_encryption, check_receives_target_public_or_same_domain,
          check_source_namespace, check_refs_into_schemas, check_sync_hop_depth]

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--catalog", type=Path, required=True)
    cat = ap.parse_args().catalog
    rc = 0
    for c in CHECKS:
        fails = c(cat)
        if fails:
            rc = 1
            for f in fails:
                print(f"FAIL {c.__name__}: {f}")
        else:
            print(f"OK   {c.__name__}")
    sys.exit(rc)
