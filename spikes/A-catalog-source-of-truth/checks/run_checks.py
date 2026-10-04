# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6", "python-frontmatter>=1.1", "jsonschema>=4"]
# ///
"""Spike A checks. Each check prints `OK <name>` or `FAIL <name>: <why> (see docs/architecture/<file>)` and the
process exits non-zero if anything failed. Each check is a function returning a list of failure strings.

    uv run checks/run_checks.py --catalog catalog [--base <catalog-on-main>] [--only check_name]
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import frontmatter, jsonschema, yaml

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from schema_diff import breaking_changes  # noqa: E402

META = json.loads((HERE / "x-pii.metaschema.json").read_text())
CENTRAL = "central-bus"


# ---------------------------------------------------------------- loading


def _x(fm, key, default=None):
    return fm.get(f"x-{key}", fm.get(key, default))


def _ids(items):
    return [(s["id"], str(s.get("version", "latest"))) if isinstance(s, dict) else (s, "latest") for s in items or []]


def load(cat: Path) -> dict:
    """A thin, independent view of the catalog (the generator has its own loader; the checks must not trust it)."""
    m = {"domains": {}, "services": {}, "events": {}, "messages": {}, "schemas": {}, "service_domain": {},
         "channel_routes": {}, "channel_fan_out": {}}
    for md in sorted(cat.glob("channels/*/index.md*")):
        fm = frontmatter.load(md)
        m["channel_routes"][fm["id"]] = [i for i, _ in _ids(fm.get("routes"))]
        m["channel_fan_out"][fm["id"]] = list(_x(fm, "fan-out-to", []) or [])
    for md in sorted(cat.glob("domains/*/index.md*")):
        fm = frontmatter.load(md)
        m["domains"][fm["id"]] = {"path": md, "services": [i for i, _ in _ids(fm.get("services"))], "fm": fm}
        for s in m["domains"][fm["id"]]["services"]:
            m["service_domain"][s] = fm["id"]
    for md in sorted(cat.glob("services/*/index.md*")):
        fm = frontmatter.load(md)
        m["services"][fm["id"]] = {
            "path": md, "fm": fm,
            "domain": _x(fm, "domain") or m["service_domain"].get(fm["id"]),
            "sends": {s["id"] if isinstance(s, dict) else s: [i for i, _ in _ids(s.get("to"))] if isinstance(s, dict) else []
                      for s in fm.get("sends") or []},
            "receives": {r["id"] if isinstance(r, dict) else r: [i for i, _ in _ids(r.get("from"))] if isinstance(r, dict) else []
                         for r in fm.get("receives") or []},
            "openapi": next((md.parent / s["path"] for s in (fm.get("specifications") or [])
                             if isinstance(s, dict) and s.get("type") == "openapi"), None)
            if isinstance(fm.get("specifications"), list)
            else (md.parent / fm["specifications"]["openapiPath"] if (fm.get("specifications") or {}).get("openapiPath") else None),
        }
    for md in sorted(cat.glob("events/*/index.md*")) + sorted(cat.glob("events/*/versioned/*/index.md*")):
        fm = frontmatter.load(md)
        sp = md.parent / (fm.get("schemaPath") or "schema.json")
        senders = [s for s, v in m["services"].items() if fm["id"] in v["sends"]]
        domain = _x(fm, "domain") or (m["services"][senders[0]]["domain"] if senders else None)
        m["events"][f"{fm['id']}@{fm['version']}"] = {
            "id": fm["id"], "version": str(fm["version"]), "path": md, "fm": fm, "domain": domain, "senders": senders,
            "visibility": _x(fm, "visibility", "internal"), "schema_path": sp,
            "schema": json.loads(sp.read_text()) if sp.exists() else None,
            "channels": sorted({c for s in senders for c in m["services"][s]["sends"][fm["id"]]} | {i for i, _ in _ids(fm.get("channels"))}),
        }
    for folder, kind in (("commands", "command"), ("queries", "query")):
        for md in sorted(cat.glob(f"{folder}/*/index.md*")):
            fm = frontmatter.load(md)
            m["messages"][fm["id"]] = {"kind": kind, "path": md, "fm": fm, "operation_id": _x(fm, "operation-id")}
    for p in sorted(cat.glob("schemas/**/*.json")):
        m["schemas"][p] = json.loads(p.read_text())
    return m


def _event_by_name(m, name):
    return [e for e in m["events"].values() if e["id"] == name]


def _deref(schema: dict, base: Path) -> dict:
    def walk(node, cur):
        if isinstance(node, dict):
            if "$ref" in node and not str(node["$ref"]).startswith("#"):
                target = (cur / node["$ref"]).resolve()
                merged = walk(json.loads(target.read_text()), target.parent)
                merged.update({k: v for k, v in node.items() if k != "$ref"})
                return merged
            return {k: walk(v, cur) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v, cur) for v in node]
        return node
    return walk(schema, base)


def _refs(schema: dict):
    if isinstance(schema, dict):
        if "$ref" in schema:
            yield schema["$ref"]
        for v in schema.values():
            yield from _refs(v)
    elif isinstance(schema, list):
        for v in schema:
            yield from _refs(v)


# ---------------------------------------------------------------- checks


def check_x_pii(cat: Path, m: dict) -> list[str]:
    """Every property in every event schema and every shared schema declares x-pii; special is forbidden;
    direct carries encryption + decryptors. Recurses into nested objects (pii.md)."""
    fails = []
    targets = [(e["schema_path"], e["schema"]) for e in m["events"].values() if e["schema"]] + list(m["schemas"].items())
    for p, schema in targets:
        for err in sorted(jsonschema.Draft202012Validator(META).iter_errors(schema), key=lambda e: list(e.absolute_path)):
            where = "/".join(str(x) for x in err.absolute_path) or "<root>"
            fails.append(f"{p.relative_to(cat)} at {where}: {err.message} (pii.md)")
    return fails


def check_direct_on_public_requires_encryption(cat: Path, m: dict) -> list[str]:
    """direct on a public event (including fields reached through $ref) requires encryption: subject-key and a
    non-empty decryptors list (pii.md). The meta-schema covers the file; this covers the dereferenced event."""
    fails = []
    for e in m["events"].values():
        if e["visibility"] != "public" or not e["schema"]:
            continue
        def walk(node, path):
            for name, prop in (node.get("properties") or {}).items():
                here = f"{path}{name}"
                if prop.get("x-pii") == "direct" and (prop.get("encryption") != "subject-key" or not prop.get("decryptors")):
                    fails.append(f"{e['id']}.{here}: direct PII on a public event needs encryption: subject-key and decryptors (pii.md)")
                if prop.get("properties"):
                    walk(prop, here + ".")
        walk(_deref(e["schema"], e["schema_path"].parent), "")
    return fails


def check_receives_target_public_or_same_domain(cat: Path, m: dict) -> list[str]:
    """A service may receive a public event, an event of its own domain, or a command/query it owns.
    Receiving another domain's internal event, or an unknown message, fails (generation-and-ci.md)."""
    fails = []
    for sname, s in m["services"].items():
        for rid in s["receives"]:
            if rid in m["messages"]:
                continue
            evs = _event_by_name(m, rid)
            if not evs:
                fails.append(f"{sname} receives {rid}, which is not an event, command or query in the catalog (generation-and-ci.md)")
                continue
            for ev in evs:
                if ev["visibility"] != "public" and ev["domain"] != s["domain"]:
                    fails.append(f"{sname} ({s['domain']}) receives internal event {rid} owned by {ev['domain']} (generation-and-ci.md)")
    return fails


def check_source_namespace(cat: Path, m: dict) -> list[str]:
    """source = {domain}.{service}: exactly one sending service, in a domain, and the declared x-source matches it
    (conventions.md)."""
    fails = []
    for e in m["events"].values():
        if len(e["senders"]) != 1:
            fails.append(f"{e['id']}: expected exactly one sending service, found {e['senders']} (conventions.md)")
            continue
        svc = e["senders"][0]
        domain = m["services"][svc]["domain"]
        if domain is None:
            fails.append(f"{e['id']}: sender {svc} is not listed under any domain (conventions.md)")
            continue
        expected = f"{domain}.{svc}"
        declared = _x(e["fm"], "source")
        if declared and declared != expected:
            fails.append(f"{e['id']}: x-source {declared!r} but the owning domain and sender give {expected!r} (conventions.md)")
        if not str(declared or expected).startswith(f"{domain}."):
            fails.append(f"{e['id']}: source must be prefixed {domain}. (conventions.md)")
    return fails


def check_channel_topology(cat: Path, m: dict) -> list[str]:
    """The bus topology is domain bus → central-bus → domain bus (README.md: fan-out-all). A service publishes every
    event to its own domain's bus and nothing else (never to central-bus directly); it receives bus events only from
    its own domain's bus; every domain bus `routes` to central-bus and central-bus `routes` to every domain bus."""
    fails = []
    bus_of = {d: _x(dom["fm"], "bus") for d, dom in m["domains"].items()}
    for sname, s in m["services"].items():
        own = bus_of.get(s["domain"])
        if own is None:
            fails.append(f"{sname}: domain {s['domain']} declares no x-bus (README.md)")
            continue
        for ev_id, to in s["sends"].items():
            if ev_id in m["messages"]:
                continue
            if set(to) != {own}:
                fails.append(f"{sname} sends {ev_id} to {to or '[]'}; events are published only to the domain's own bus {own} (README.md)")
        for ev_id, frm in s["receives"].items():
            if ev_id in m["messages"]:
                continue
            if set(frm) != {own}:
                fails.append(f"{sname} receives {ev_id} from {frm or '[]'}; consumers subscribe only on their own bus {own} (README.md)")
    routes = m["channel_routes"]
    if CENTRAL not in routes:
        return fails + [f"channel {CENTRAL} is missing (README.md)"]
    # The fan-out hop is declared as x-fan-out-to on central-bus, not as routes: EventCatalog 4.12.3 overflows when
    # central routes back to two or more buses that route into it. If routes are present they must be complete.
    fan_out = set(m["channel_fan_out"].get(CENTRAL, [])) | set(routes[CENTRAL])
    for d, bus in bus_of.items():
        if bus is None:
            continue
        if CENTRAL not in routes.get(bus, []):
            fails.append(f"channel {bus} ({d}) must route to {CENTRAL} (public-forward rule) (README.md)")
        if bus not in fan_out:
            fails.append(f"channel {CENTRAL} must fan out to {bus} ({d}): list it under x-fan-out-to or routes (README.md)")
    return fails


def check_refs_into_schemas(cat: Path, m: dict) -> list[str]:
    """Every $ref resolves to a file under schemas/; files at the schemas/ root are value objects, never entities
    (an entity declares x-kind: entity or carries its own identity field) (conventions.md, generation-and-ci.md)."""
    fails = []
    schemas_root = (cat / "schemas").resolve()
    sources = [(e["schema_path"], e["schema"]) for e in m["events"].values() if e["schema"]] + list(m["schemas"].items())
    for svc in m["services"].values():
        if svc["openapi"] and svc["openapi"].exists():
            sources.append((svc["openapi"], yaml.safe_load(svc["openapi"].read_text())))
    for p, schema in sources:
        for ref in _refs(schema):
            if str(ref).startswith("#"):
                continue
            target = (p.parent / ref).resolve()
            if not target.exists():
                fails.append(f"{p.relative_to(cat)}: $ref {ref} does not resolve (generation-and-ci.md)")
            elif not target.is_relative_to(schemas_root):
                fails.append(f"{p.relative_to(cat)}: $ref {ref} resolves outside schemas/ (generation-and-ci.md)")
    for p, schema in m["schemas"].items():
        if p.resolve().parent != schemas_root:
            continue
        name = p.stem
        identity = f"{name[0].lower()}{name[1:]}Id"
        if schema.get("x-kind") == "entity" or identity in (schema.get("properties") or {}):
            fails.append(f"schemas/{p.name}: entity at the shared root; move it to schemas/<domain>/ (generation-and-ci.md)")
    return fails


def check_openapi_operations_have_pages(cat: Path, m: dict) -> list[str]:
    """Every operation declares x-eventcatalog-message-type and has a command/query page of the same kind whose id is
    the operationId, received by the service that owns the spec (conventions.md, ADR-004). Core EventCatalog does
    not derive these pages from OpenAPI without the Scale plugin, so the check keeps them honest."""
    fails = []
    for sname, s in m["services"].items():
        if not s["openapi"]:
            continue
        spec = yaml.safe_load(s["openapi"].read_text())
        for path, ops in (spec.get("paths") or {}).items():
            for method, op in ops.items():
                if method not in ("get", "post", "put", "patch", "delete"):
                    continue
                kind = op.get("x-eventcatalog-message-type")
                oid = op.get("operationId")
                if kind not in ("command", "query"):
                    fails.append(f"{sname} {method.upper()} {path}: missing x-eventcatalog-message-type (conventions.md)")
                    continue
                page = m["messages"].get(oid)
                if page is None:
                    fails.append(f"{sname} {method.upper()} {path}: no {kind} page with id {oid} (ADR-004)")
                elif page["kind"] != kind:
                    fails.append(f"{sname} {oid}: spec says {kind}, page is a {page['kind']} (ADR-004)")
                elif oid not in s["receives"]:
                    fails.append(f"{sname}: must list {oid} under receives[] (ADR-004)")
    return fails


def check_sync_hop_depth(cat: Path, m: dict) -> list[str]:
    """Caller → provider edges from commands/queries (caller sends, provider receives). Any path of length 2 or more,
    or a cycle, fails: one synchronous hop between domains (ADR-002)."""
    fails = []
    provider = {mid: [s for s, v in m["services"].items() if mid in v["receives"]] for mid in m["messages"]}
    edges: dict[str, set[str]] = {}
    for sname, s in m["services"].items():
        for mid in s["sends"]:
            if mid in m["messages"]:
                for p in provider.get(mid, []):
                    if p != sname:
                        edges.setdefault(sname, set()).add(p)
    for a, bs in sorted(edges.items()):
        for b in sorted(bs):
            for c in sorted(edges.get(b, ())):
                fails.append(f"sync chain {a} -> {b} -> {c} is deeper than one hop (ADR-002)")
    return fails


def check_examples_match_schema(cat: Path, m: dict) -> list[str]:
    """Every examples/*.json is a full EventBridge envelope whose detail validates against Envelope + payload, with
    direct fields of public events as ciphertext envelopes; source and detail-type match the catalog (conventions.md)."""
    fails = []
    envelope = next((s for p, s in m["schemas"].items() if p.name == "Envelope.json"), None)
    if envelope is None:
        return ["schemas/Envelope.json missing (conventions.md)"]
    cipher = {"type": "object", "required": ["enc", "kid", "ct"], "properties": {"enc": {"const": "v1"}, "kid": {"type": "string"}, "ct": {"type": "string"}}}

    def wire(node):
        out = dict(node)
        out["properties"] = {k: (cipher if v.get("x-pii") == "direct" else wire(v) if v.get("properties") else v)
                             for k, v in (node.get("properties") or {}).items()}
        return out

    for e in m["events"].values():
        if not e["schema"]:
            continue
        payload = _deref(e["schema"], e["schema_path"].parent)
        if e["visibility"] == "public":
            payload = wire(payload)
        schema = {"type": "object", "additionalProperties": False,
                  "properties": {**envelope.get("properties", {}), **payload.get("properties", {})},
                  "required": sorted(set(envelope.get("required") or []) | set(payload.get("required") or []))}
        for ex in sorted(e["path"].parent.glob("examples/*.json")):
            doc = json.loads(ex.read_text())
            expected_dt = f"{e['id']}.v{e['version'].split('.')[0]}"
            if doc.get("detail-type") != expected_dt:
                fails.append(f"{ex.relative_to(cat)}: detail-type {doc.get('detail-type')!r} != {expected_dt!r} (conventions.md)")
            if e["senders"] and doc.get("source") != f"{e['domain']}.{e['senders'][0]}":
                fails.append(f"{ex.relative_to(cat)}: source {doc.get('source')!r} != {e['domain']}.{e['senders'][0]} (conventions.md)")
            for err in jsonschema.Draft202012Validator(schema).iter_errors(doc.get("detail", {})):
                fails.append(f"{ex.relative_to(cat)}: detail/{'/'.join(map(str, err.absolute_path))}: {err.message} (conventions.md)")
    return fails


def check_schema_diff(cat: Path, m: dict, base: Path | None = None) -> list[str]:
    """Breaking change (removed field, type change, newly required, narrowed enum) to a public event's schema
    under the same version fails: declare .v{n+1} instead (generation-and-ci.md). Needs --base <catalog on main>."""
    if base is None:
        return []
    fails = []
    for key, e in m["events"].items():
        old = base / e["schema_path"].relative_to(cat)
        if not old.exists() or not e["schema"]:
            continue
        for change in breaking_changes(_deref(json.loads(old.read_text()), old.parent), _deref(e["schema"], e["schema_path"].parent)):
            fails.append(f"{e['id']} v{e['version']}: {change}; a breaking change needs a new version (generation-and-ci.md)")
    return fails


CHECKS = [check_x_pii, check_direct_on_public_requires_encryption, check_receives_target_public_or_same_domain,
          check_source_namespace, check_channel_topology, check_refs_into_schemas,
          check_openapi_operations_have_pages, check_sync_hop_depth, check_examples_match_schema, check_schema_diff]


def run(cat: Path, base: Path | None = None, only: str | None = None) -> dict[str, list[str]]:
    m = load(cat)
    results = {}
    for c in CHECKS:
        if only and c.__name__ != only:
            continue
        results[c.__name__] = c(cat, m, base) if c is check_schema_diff else c(cat, m)
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", type=Path, required=True)
    ap.add_argument("--base", type=Path, help="catalog as on main, for the schema diff")
    ap.add_argument("--only")
    a = ap.parse_args()
    rc = 0
    for name, fails in run(a.catalog, a.base, a.only).items():
        if fails:
            rc = 1
            for f in fails:
                print(f"FAIL {name}: {f}")
        else:
            print(f"OK   {name}")
    sys.exit(rc)
