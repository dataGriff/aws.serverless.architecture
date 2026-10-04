# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6", "python-frontmatter>=1.1", "jsonschema>=4"]
# ///
"""catalog-gen — Spike A skeleton.

Plumbing is done: catalog loading, deterministic writer, `build`, `check`, `explain`.
The spike's work is the emitters marked TODO; each returns {relative_path: content_str}.

    uv run catalog_gen.py build   --catalog ../catalog --out ../generated/local
    uv run catalog_gen.py check   --catalog ../catalog --out ../generated/local
    uv run catalog_gen.py explain --catalog ../catalog --out ../generated/local rules/orders-fan-out.json
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter
import yaml

# ---------------------------------------------------------------- model


@dataclass
class Event:
    name: str            # OrderPlaced
    version: str         # 1
    domain: str
    source_prefix: str   # orders.
    visibility: str      # public | internal
    audience: str        # all | restricted
    schema: dict
    overlay: dict | None
    path: Path

    @property
    def detail_type(self) -> str:
        return f"{self.name}.v{self.version}"


@dataclass
class Service:
    name: str
    domain: str
    sends: list[str]
    receives: list[str]
    openapi: Path | None
    path: Path


@dataclass
class Domain:
    name: str
    owners: list[str]
    path: Path


@dataclass
class Catalog:
    domains: dict[str, Domain] = field(default_factory=dict)
    services: dict[str, Service] = field(default_factory=dict)
    events: dict[str, Event] = field(default_factory=dict)   # key = detail_type

    def public_events(self, domain: str) -> list[Event]:
        return sorted((e for e in self.events.values() if e.domain == domain and e.visibility == "public"),
                      key=lambda e: e.detail_type)


def load(catalog_dir: Path) -> Catalog:
    """Walk the EventCatalog folder layout. Adjust globs to the installed version's conventions."""
    cat = Catalog()
    for md in sorted(catalog_dir.glob("domains/*/index.md*")):
        fm = frontmatter.load(md)
        cat.domains[fm["id"]] = Domain(fm["id"], list(fm.get("owners", [])), md.parent)
    for md in sorted(catalog_dir.glob("services/*/index.md*")):
        fm = frontmatter.load(md)
        spec = fm.get("specifications", {}).get("openapiPath")
        cat.services[fm["id"]] = Service(
            fm["id"], fm.get("domain") or _domain_of(md, cat),
            [s["id"] if isinstance(s, dict) else s for s in fm.get("sends", [])],
            [r["id"] if isinstance(r, dict) else r for r in fm.get("receives", [])],
            md.parent / spec if spec else None, md.parent)
    for md in sorted(catalog_dir.glob("events/*/versioned/*/index.md*")) + sorted(catalog_dir.glob("events/*/index.md*")):
        fm = frontmatter.load(md)
        schema_path = md.parent / "schema.json"
        if not schema_path.exists():
            continue
        overlay_path = md.parent / "data-product.yaml"
        domain = fm.get("domain") or _domain_of(md, cat)
        ev = Event(name=fm["id"], version=str(fm["version"]).split(".")[0], domain=domain,
                   source_prefix=f"{domain}.", visibility=fm.get("visibility", "internal"),
                   audience=fm.get("audience", "all"), schema=json.loads(schema_path.read_text()),
                   overlay=yaml.safe_load(overlay_path.read_text()) if overlay_path.exists() else None,
                   path=md.parent)
        cat.events[ev.detail_type] = ev
    return cat


def _domain_of(md: Path, cat: Catalog) -> str:
    # Fallback: infer from a `domain:` field or from the folder name; spike decides the convention.
    return md.parent.name.split("-")[0]


# ---------------------------------------------------------------- emitters (TODO: the spike's work)

def emit_rules(cat: Catalog) -> dict[str, str]:
    out: dict[str, str] = {}
    domains = sorted(cat.domains)
    for d in domains:
        public = [e.detail_type for e in cat.public_events(d)]
        out[f"rules/{d}-public-forward.json"] = _j({"source": [{"prefix": f"{d}."}], "detail-type": public})
        out[f"rules/{d}-fan-out.json"] = _j({"source": [{"anything-but": {"prefix": f"{d}."}}]})
        out[f"rules/{d}-fan-out.enumerated.json"] = _j({"source": [{"prefix": f"{o}."} for o in domains if o != d]})
    # TODO: consumer rules from services[].receives -> rules/{domain}-consumer-{event}.json
    # TODO: split any pattern that exceeds 4096 bytes into -part-N files and record it in the manifest
    return out


def emit_routing_map(cat: Catalog) -> dict[str, str]:
    return {"archive/routing-map.json": _j({f"{d}.": f"{d}-events-bronze" for d in sorted(cat.domains)})}


def emit_validation_bundles(cat: Catalog) -> dict[str, str]:
    # TODO: per domain: {detail_type: schema} plus the list of x-pii: direct field paths that must be ciphertext
    return {}


def emit_parquet_schemas(cat: Catalog) -> dict[str, str]:
    # TODO: per public event: envelope columns + d_<field> for x-pii none|indirect, types per data-layer.md
    return {}


def emit_odcs(cat: Catalog) -> dict[str, str]:
    # TODO: per public event: ODCS v3 from schema + x-pii + owners, deep-merged with data-product.yaml overlay
    return {}


def emit_manifest(cat: Catalog, files: dict[str, str]) -> dict[str, str]:
    order = ["schemas", "rules/*-public-forward*", "rules/*-fan-out*", "rules/*-consumer-*", "archive", "contracts", "clients"]
    return {"deploy-order.json": _j({"order": order, "files": sorted(files)})}


EMITTERS = [emit_rules, emit_routing_map, emit_validation_bundles, emit_parquet_schemas, emit_odcs]

# ---------------------------------------------------------------- plumbing


def _j(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def generate(cat: Catalog) -> dict[str, str]:
    files: dict[str, str] = {}
    for em in EMITTERS:
        for k, v in em(cat).items():
            if k in files:
                raise SystemExit(f"two emitters wrote {k}")
            files[k] = v
    files.update(emit_manifest(cat, files))
    return dict(sorted(files.items()))


def write(files: dict[str, str], out: Path) -> None:
    for p in out.rglob("*"):
        if p.is_file() and str(p.relative_to(out)) not in files:
            p.unlink()
    for rel, content in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists() or p.read_text() != content:
            p.write_text(content)


def check(files: dict[str, str], out: Path) -> int:
    on_disk = {str(p.relative_to(out)): p.read_text() for p in out.rglob("*") if p.is_file()}
    bad = 0
    for rel in sorted(set(files) | set(on_disk)):
        a, b = on_disk.get(rel), files.get(rel)
        if a != b:
            bad += 1
            print(f"DRIFT {rel}")
            if a and b:
                sys.stdout.writelines(difflib.unified_diff(a.splitlines(True), b.splitlines(True), "on-disk", "generated"))
    return 1 if bad else 0


def explain(cat: Catalog, rel: str) -> None:
    # Spike: make this precise. A decent first cut: name the emitter and the catalog entries whose ids appear in the path.
    for em in EMITTERS:
        if rel in em(cat):
            print(f"{rel} <- {em.__name__}")
            for k, e in cat.events.items():
                if e.domain in rel or k in rel:
                    print(f"  event {k}  ({e.path})")
            return
    print("not generated")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "check", "explain"])
    ap.add_argument("--catalog", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("path", nargs="?")
    a = ap.parse_args()
    cat = load(a.catalog)
    files = generate(cat)
    if a.cmd == "build":
        write(files, a.out)
        digest = hashlib.sha256("".join(f"{k}{v}" for k, v in files.items()).encode()).hexdigest()[:12]
        print(f"wrote {len(files)} files to {a.out} (digest {digest})")
        return 0
    if a.cmd == "check":
        return check(files, a.out)
    explain(cat, a.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
