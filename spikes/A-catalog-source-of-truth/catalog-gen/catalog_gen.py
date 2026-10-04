# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6", "python-frontmatter>=1.1", "jsonschema>=4"]
# ///
"""catalog-gen — Spike A.

Reads an EventCatalog folder and writes deterministic JSON/YAML. Everything goes under --out except the ODCS
contracts, which are written beside their event inside the catalog (data-contracts.md) so the site can render them;
`check` covers both locations.

    rules/{domain}-public-forward.json          detail-type list of the domain's public events (split at --pattern-limit)
    rules/{domain}-fan-out.json                 source anything-but own prefix
    rules/{domain}-fan-out.enumerated.json      source prefix list of every other domain
    rules/{domain}-consumer-{event}.json        consumer rule on the domain's own bus, from services[].receives
    archive/routing-map.json                    source prefix -> bronze bucket + public detail-types
    validation/{domain}.json                    envelope+payload schema per public event, direct fields as ciphertext envelopes
    parquet/{DetailType}.json                   silver column list per public event
    catalog/events/{Event}/odcs.yaml            ODCS v3 per public event, merged with data-product.yaml  (written into the catalog)
    deploy-order.json                           apply order, file list, consumer targets, split parts

    uv run catalog_gen.py build   --catalog ../catalog --out ../generated/local
    uv run catalog_gen.py check   --catalog ../catalog --out ../generated/local
    uv run catalog_gen.py explain --catalog ../catalog --out ../generated/local rules/orders-fan-out.json
"""
from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter
import yaml

CATALOG_PREFIX = "catalog/"   # generated files written into the catalog instead of --out
ENVELOPE_COLUMNS = [
    ("id", "string"), ("source", "string"), ("detail_type", "string"), ("bus_time", "timestamp[us,UTC]"),
    ("event_id", "string"), ("occurred_at", "timestamp[us,UTC]"), ("correlation_id", "string"),
    ("causation_id", "string"), ("aggregate_id", "string"), ("aggregate_version", "int64"),
    ("replay", "bool"), ("pii_class", "string"),
]
ENVELOPE_NULLABLE = {"correlation_id", "causation_id"}
ENVELOPE_CLASS = {"aggregate_id": "indirect"}
PII_RANK = {"none": 0, "indirect": 1, "direct": 2, "special": 3}
ODCS_OVERLAY_KEYS = {"description", "slaProperties", "team", "quality", "terms", "customProperties",
                     "tags", "support", "price", "authoritativeDefinitions"}
CIPHERTEXT_ENVELOPE = {
    "type": "object",
    "description": "Subject-key ciphertext envelope (conventions.md)",
    "properties": {"enc": {"const": "v1"}, "kid": {"type": "string", "minLength": 1},
                   "ct": {"type": "string", "contentEncoding": "base64", "minLength": 1}},
    "required": ["enc", "kid", "ct"],
    "additionalProperties": False,
}

# ---------------------------------------------------------------- model


@dataclass
class Event:
    name: str            # OrderPlaced
    version: str         # 1
    domain: str
    service: str         # order-service
    visibility: str      # public | internal
    audience: str        # all | restricted
    schema: dict
    overlay: dict | None
    path: Path
    schema_path: Path
    overlay_path: Path | None
    deprecated: bool = False
    declared_source: str | None = None
    channels: list[str] = field(default_factory=list)

    @property
    def detail_type(self) -> str:
        return f"{self.name}.v{self.version}"

    @property
    def source(self) -> str:
        return f"{self.domain}.{self.service}"

    @property
    def source_prefix(self) -> str:
        return f"{self.domain}."


@dataclass
class Service:
    name: str
    domain: str
    sends: list[tuple[str, str]]      # (id, version)
    receives: list[tuple[str, str]]
    openapi: Path | None
    path: Path


@dataclass
class Domain:
    name: str
    owners: list[str]
    services: list[str]
    path: Path


@dataclass
class Message:
    """A command or query page."""
    name: str
    kind: str   # command | query
    operation_id: str | None
    path: Path


@dataclass
class Catalog:
    root: Path
    domains: dict[str, Domain] = field(default_factory=dict)
    services: dict[str, Service] = field(default_factory=dict)
    events: dict[str, Event] = field(default_factory=dict)   # key = detail_type
    messages: dict[str, Message] = field(default_factory=dict)
    schemas: dict[str, dict] = field(default_factory=dict)   # shared schemas by path relative to root

    def public_events(self, domain: str) -> list[Event]:
        return sorted((e for e in self.events.values() if e.domain == domain and e.visibility == "public"),
                      key=lambda e: e.detail_type)

    def events_named(self, name: str) -> list[Event]:
        return sorted((e for e in self.events.values() if e.name == name), key=lambda e: int(e.version))


def _ids(items) -> list[tuple[str, str]]:
    out = []
    for s in items or []:
        if isinstance(s, dict):
            out.append((s["id"], str(s.get("version", "latest"))))
        else:
            out.append((s, "latest"))
    return out


def _x(fm, key: str, default=None):
    """Platform keys are `x-` prefixed in EventCatalog frontmatter (unknown top-level keys fail the build);
    the bare key is accepted too for fixtures."""
    return fm.get(f"x-{key}", fm.get(key, default))


def load(catalog_dir: Path) -> Catalog:
    cat = Catalog(root=catalog_dir)
    service_domain: dict[str, str] = {}
    for md in sorted(catalog_dir.glob("domains/*/index.md*")):
        fm = frontmatter.load(md)
        svcs = [i for i, _ in _ids(fm.get("services"))]
        cat.domains[fm["id"]] = Domain(fm["id"], list(fm.get("owners", [])), svcs, md.parent)
        for s in svcs:
            service_domain[s] = fm["id"]
    for md in sorted(catalog_dir.glob("services/*/index.md*")):
        fm = frontmatter.load(md)
        specs = fm.get("specifications") or {}
        if isinstance(specs, list):
            spec = next((s.get("path") for s in specs if isinstance(s, dict) and s.get("type") == "openapi"), None)
        else:
            spec = specs.get("openapiPath")
        domain = _x(fm, "domain") or service_domain.get(fm["id"])
        if domain is None:
            raise SystemExit(f"{md}: service {fm['id']} is not listed by any domain and has no x-domain: key")
        cat.services[fm["id"]] = Service(fm["id"], domain, _ids(fm.get("sends")), _ids(fm.get("receives")),
                                         md.parent / spec if spec else None, md.parent)
    sender: dict[str, Service] = {}
    sent_to: dict[str, list[str]] = {}
    for md in sorted(catalog_dir.glob("services/*/index.md*")):
        fm = frontmatter.load(md)
        for s in fm.get("sends") or []:
            if isinstance(s, dict):
                sent_to.setdefault(s["id"], []).extend(i for i, _ in _ids(s.get("to")))
    for s in cat.services.values():
        for ev, _ in s.sends:
            sender.setdefault(ev, s)
    for p in sorted(catalog_dir.glob("schemas/**/*.json")):
        cat.schemas[str(p.relative_to(catalog_dir))] = json.loads(p.read_text())
    for md in sorted(catalog_dir.glob("events/*/index.md*")) + sorted(catalog_dir.glob("events/*/versioned/*/index.md*")):
        fm = frontmatter.load(md)
        schema_path = md.parent / (fm.get("schemaPath") or "schema.json")
        if not schema_path.exists():
            continue
        overlay_path = md.parent / "data-product.yaml"
        svc = sender.get(fm["id"])
        domain = _x(fm, "domain") or (svc.domain if svc else None)
        if domain is None:
            raise SystemExit(f"{md}: event {fm['id']} has no sending service and no x-domain: key")
        ev = Event(name=fm["id"], version=str(fm["version"]).split(".")[0], domain=domain,
                   service=svc.name if svc else "unknown", visibility=_x(fm, "visibility", "internal"),
                   audience=_x(fm, "audience", "all"), schema=json.loads(schema_path.read_text()),
                   overlay=yaml.safe_load(overlay_path.read_text()) if overlay_path.exists() else None,
                   path=md.parent, schema_path=schema_path, overlay_path=overlay_path if overlay_path.exists() else None,
                   deprecated=bool(fm.get("deprecated")), declared_source=_x(fm, "source"),
                   channels=sorted(set(sent_to.get(fm["id"], [])) | {i for i, _ in _ids(fm.get("channels"))}))
        cat.events[ev.detail_type] = ev
    for folder, kind in (("commands", "command"), ("queries", "query")):
        for md in sorted(catalog_dir.glob(f"{folder}/*/index.md*")):
            fm = frontmatter.load(md)
            cat.messages[fm["id"]] = Message(fm["id"], kind, _x(fm, "operation-id"), md.parent)
    return cat


# ---------------------------------------------------------------- schema helpers


def deref(schema: dict, base: Path) -> dict:
    """Inline every relative-file $ref so the result stands alone. Sibling keys of $ref win."""
    def walk(node, cur: Path):
        if isinstance(node, dict):
            if "$ref" in node and not str(node["$ref"]).startswith("#"):
                target = (cur / node["$ref"]).resolve()
                merged = walk(json.loads(target.read_text()), target.parent)
                merged.update({k: v for k, v in node.items() if k != "$ref"})
                merged.pop("$id", None)
                merged.pop("$schema", None)
                return merged
            return {k: walk(v, cur) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v, cur) for v in node]
        return node
    return walk(copy.deepcopy(schema), base)


def ref_sources(schema: dict, base: Path) -> list[Path]:
    found: list[Path] = []

    def walk(node, cur: Path):
        if isinstance(node, dict):
            if "$ref" in node and not str(node["$ref"]).startswith("#"):
                target = (cur / node["$ref"]).resolve()
                found.append(target)
                walk(json.loads(target.read_text()), target.parent)
            for v in node.values():
                walk(v, cur)
        elif isinstance(node, list):
            for v in node:
                walk(v, cur)
    walk(schema, base)
    return sorted(set(found))


def pii_fields(schema: dict, prefix: str = "") -> list[tuple[str, str]]:
    """(dotted path, class) for every property, recursing into nested objects. Schema must be dereferenced."""
    out = []
    for name, prop in (schema.get("properties") or {}).items():
        path = f"{prefix}{name}"
        if "x-pii" in prop:
            out.append((path, prop["x-pii"]))
        if prop.get("properties"):
            out.extend(pii_fields(prop, path + "."))
    return out


def ciphertext_form(schema: dict) -> dict:
    """On the wire, every direct field of a public event is the ciphertext envelope, whatever its logical type."""
    out = copy.deepcopy(schema)
    for name, prop in (out.get("properties") or {}).items():
        if prop.get("x-pii") == "direct":
            keep = {k: prop[k] for k in ("x-pii", "encryption", "decryptors", "description") if k in prop}
            out["properties"][name] = {**CIPHERTEXT_ENVELOPE, **keep}
        elif prop.get("properties"):
            out["properties"][name] = ciphertext_form(prop)
    return out


def snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name.replace(".", "_").replace("-", "_")).lower()


def kebab(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name.replace(".", "-").replace("_", "-")).lower()


def arrow_type(prop: dict) -> str | None:
    t, f = prop.get("type"), prop.get("format")
    if prop.get("title") == "Money" or f == "decimal":
        return "decimal128(18,4)"
    if t == "string":
        return {"date": "date32", "date-time": "timestamp[us,UTC]"}.get(f, "string")
    if t == "integer":
        return "int64"
    if t == "number":
        return "double"
    if t == "boolean":
        return "bool"
    if t == "object" and prop.get("properties"):
        return "struct"
    if t == "array":
        return "list"
    return None


def silver_columns(ev: Event) -> tuple[list[dict], str]:
    schema = deref(ev.schema, ev.schema_path.parent)
    cols = [{"name": n, "type": t, "nullable": n in ENVELOPE_NULLABLE, "classification": ENVELOPE_CLASS.get(n, "none")}
            for n, t in ENVELOPE_COLUMNS]
    highest = "none"
    for _, cls in pii_fields(schema):
        if PII_RANK[cls] > PII_RANK[highest]:
            highest = cls
    cols.append({"name": "detail", "type": "string", "nullable": False, "classification": highest,
                 "description": "Full payload as JSON; direct fields are ciphertext envelopes"})
    required = set(schema.get("required") or [])
    for name, prop in (schema.get("properties") or {}).items():
        cls = prop.get("x-pii", "none")
        if cls not in ("none", "indirect"):
            continue
        if prop.get("title") == "Money":
            cols.append({"name": f"d_{snake(name)}", "type": "decimal128(18,4)", "nullable": name not in required, "classification": cls})
            cols.append({"name": f"d_{snake(name)}_currency", "type": "string", "nullable": name not in required, "classification": cls})
            continue
        t = arrow_type(prop)
        if t is None:
            continue
        cols.append({"name": f"d_{snake(name)}", "type": t, "nullable": name not in required, "classification": cls})
    return cols, highest


# ---------------------------------------------------------------- emitters

PROVENANCE: dict[str, list[str]] = {}
PATTERN_LIMIT = 4096


def _emit(out: dict[str, str], rel: str, content: str, sources: list[Path]) -> None:
    if rel in out:
        raise SystemExit(f"two emitters wrote {rel}")
    out[rel] = content
    PROVENANCE[rel] = sorted({str(s) for s in sources})


def _split_detail_types(prefix: str, detail_types: list[str]) -> list[list[str]]:
    parts, cur = [], []
    for dt in detail_types:
        cur.append(dt)
        if len(_compact({"source": [{"prefix": prefix}], "detail-type": cur})) >= PATTERN_LIMIT and len(cur) > 1:
            cur.pop()
            parts.append(cur)
            cur = [dt]
    parts.append(cur)
    return parts


def emit_rules(cat: Catalog) -> dict[str, str]:
    out: dict[str, str] = {}
    domains = sorted(cat.domains)
    domain_paths = [x.path for x in cat.domains.values()]
    for d in domains:
        public = cat.public_events(d)
        parts = _split_detail_types(f"{d}.", [e.detail_type for e in public])
        srcs = [cat.domains[d].path] + [e.path for e in public]
        if len(parts) == 1:
            _emit(out, f"rules/{d}-public-forward.json", _j({"source": [{"prefix": f"{d}."}], "detail-type": parts[0]}), srcs)
        else:
            for i, part in enumerate(parts, 1):
                _emit(out, f"rules/{d}-public-forward.part-{i}.json",
                      _j({"source": [{"prefix": f"{d}."}], "detail-type": part}), srcs)
        _emit(out, f"rules/{d}-fan-out.json", _j({"source": [{"anything-but": {"prefix": f"{d}."}}]}), domain_paths)
        _emit(out, f"rules/{d}-fan-out.enumerated.json", _j({"source": [{"prefix": f"{o}."} for o in domains if o != d]}), domain_paths)
    for rel, (pattern, sources) in _consumer_rules(cat).items():
        _emit(out, rel, _j(pattern), sources)
    return out


def _consumer_rules(cat: Catalog) -> dict[str, tuple[dict, list[Path]]]:
    """One rule per (consuming domain, event name) on the domain's own bus; received versions collapse into detail-type.
    Commands and queries in receives[] are API operations, not bus subscriptions, and produce no rule."""
    by_key: dict[tuple[str, str], dict] = {}
    for svc in sorted(cat.services.values(), key=lambda s: s.name):
        for ev_id, ver in svc.receives:
            if ev_id in cat.messages:
                continue
            known = cat.events_named(ev_id)
            entry = by_key.setdefault((svc.domain, ev_id), {"detail_types": set(), "sources": set(), "paths": {svc.path}})
            entry["paths"].add(svc.path)
            if not known:
                major = ver.lstrip("^").split(".")[0]
                entry["detail_types"].add(f"{ev_id}.v{major if major != 'latest' else '1'}")
                continue
            versions = [e for e in known if ver in ("latest", e.version, f"^{e.version}") or ver.split(".")[0] == e.version] or known[-1:]
            for e in versions:
                entry["detail_types"].add(e.detail_type)
                entry["sources"].add(e.source_prefix)
                entry["paths"].add(e.path)
    out = {}
    for (domain, ev_id), entry in sorted(by_key.items()):
        pattern: dict = {"detail-type": sorted(entry["detail_types"])}
        if entry["sources"]:
            pattern["source"] = [{"prefix": p} for p in sorted(entry["sources"])]
        out[f"rules/{domain}-consumer-{kebab(ev_id)}.json"] = (pattern, sorted(entry["paths"]))
    return out


def consumer_targets(cat: Catalog) -> dict[str, list[str]]:
    targets: dict[str, set[str]] = {}
    for svc in cat.services.values():
        for ev_id, _ in svc.receives:
            if ev_id not in cat.messages:
                targets.setdefault(f"rules/{svc.domain}-consumer-{kebab(ev_id)}.json", set()).add(svc.name)
    return {k: sorted(v) for k, v in sorted(targets.items())}


def emit_routing_map(cat: Catalog) -> dict[str, str]:
    out: dict[str, str] = {}
    m = {f"{d}.": {"bucket": f"{d}-events-bronze", "detailTypes": [e.detail_type for e in cat.public_events(d)]}
         for d in sorted(cat.domains)}
    _emit(out, "archive/routing-map.json", _j(m),
          [x.path for x in cat.domains.values()] + [e.path for e in cat.events.values() if e.visibility == "public"])
    return out


def _envelope(cat: Catalog) -> dict:
    env = cat.schemas.get("schemas/Envelope.json")
    if env is None:
        raise SystemExit("schemas/Envelope.json is required (conventions.md: inside detail)")
    return {k: v for k, v in env.items() if k not in ("$id", "$schema")}


def compose_detail(envelope: dict, payload: dict) -> dict:
    """Flatten envelope + payload into one closed object. `allOf` cannot be used: a payload with
    additionalProperties: false would reject the envelope fields (and vice versa)."""
    clash = sorted(set(envelope.get("properties") or {}) & set(payload.get("properties") or {}))
    if clash:
        raise SystemExit(f"{payload.get('title')}: payload fields {clash} collide with envelope fields (conventions.md)")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"{payload.get('title', 'event')} (detail)",
        "type": "object",
        "properties": {**envelope.get("properties", {}), **payload.get("properties", {})},
        "required": sorted(set(envelope.get("required") or []) | set(payload.get("required") or [])),
        "additionalProperties": False,
    }


def emit_validation_bundles(cat: Catalog) -> dict[str, str]:
    out: dict[str, str] = {}
    envelope = _envelope(cat)
    for d in sorted(cat.domains):
        bundle, srcs = {}, [cat.domains[d].path, cat.root / "schemas/Envelope.json"]
        for ev in cat.public_events(d):
            payload = deref(ev.schema, ev.schema_path.parent)
            srcs += [ev.path, ev.schema_path] + ref_sources(ev.schema, ev.schema_path.parent)
            bundle[ev.detail_type] = {
                "source": ev.source,
                "schema": compose_detail(envelope, ciphertext_form(payload)),
                "ciphertextFields": sorted(p for p, c in pii_fields(payload) if c == "direct"),
            }
        if bundle:
            _emit(out, f"validation/{d}.json", _j(bundle), srcs)
    return out


def emit_parquet_schemas(cat: Catalog) -> dict[str, str]:
    out: dict[str, str] = {}
    for ev in sorted(cat.events.values(), key=lambda e: e.detail_type):
        if ev.visibility != "public":
            continue
        cols, highest = silver_columns(ev)
        _emit(out, f"parquet/{ev.detail_type}.json", _j({
            "table": f"silver/{ev.source}/{ev.detail_type}/",
            "partitioning": ["dt", "hour"],
            "piiClassMax": highest,
            "columns": cols,
        }), [ev.path, ev.schema_path] + ref_sources(ev.schema, ev.schema_path.parent))
    return out


def odcs_contract(cat: Catalog, ev: Event) -> dict:
    cols, highest = silver_columns(ev)
    owners = cat.domains[ev.domain].owners
    schema = deref(ev.schema, ev.schema_path.parent)
    props = []
    for c in cols:
        p = {"name": c["name"], "logicalType": _odcs_logical(c["type"]), "physicalType": c["type"],
             "required": not c["nullable"], "classification": c["classification"]}
        if c["name"] == "event_id":
            p.update(unique=True, primaryKey=True)
        if c.get("description"):
            p["description"] = c["description"]
        props.append(p)
    direct = [n for n, cl in pii_fields(schema) if cl == "direct"]
    decryptors = sorted({d for prop in (schema.get("properties") or {}).values()
                         if prop.get("x-pii") == "direct" for d in prop.get("decryptors", [])})
    table = f"{ev.domain}_{snake(ev.name)}_v{ev.version}"
    contract = {
        "apiVersion": "v3.0.2",
        "kind": "DataContract",
        "id": f"{ev.domain}.{ev.name}.v{ev.version}",
        "name": f"{ev.domain} · {ev.name} v{ev.version} · silver",
        "version": f"{ev.version}.0.0",
        "status": "deprecated" if ev.deprecated else "active",
        "domain": ev.domain,
        "dataProduct": f"{ev.domain}-events-silver",
        "tenant": "platform",
        "description": {
            "purpose": f"Analytical copy of every public {ev.detail_type} event, one row per eventId.",
            "limitations": ("direct PII fields are ciphertext inside detail; request a decryptor grant via the catalog."
                            if direct else "No direct PII in this event."),
            "usage": f"Query the DuckDB view silver_{table}; always filter on dt.",
        },
        "schema": [{
            "name": table,
            "physicalType": "parquet",
            "physicalName": f"silver/{ev.source}/{ev.detail_type}/",
            "properties": props,
            "quality": [
                {"type": "library", "rule": "duplicateCount", "column": "event_id", "mustBe": 0},
                {"type": "sql", "query": "SELECT count(*) FROM ${object} WHERE occurred_at IS NULL", "mustBe": 0},
                {"type": "custom", "engine": "platform-checks", "implementation": "partitionCompleteness(min=0.999)"},
            ],
        }],
        "servers": [
            {"server": "local", "type": "s3", "environment": "local", "format": "parquet",
             "location": f"s3://{ev.domain}-events-silver-local/silver/{ev.source}/{ev.detail_type}/"},
        ],
        "slaProperties": [
            {"property": "latency", "value": 3, "unit": "h", "element": f"{table}.occurred_at"},
            {"property": "frequency", "value": 1, "unit": "h"},
        ],
        "team": [{"username": o, "role": "owner"} for o in owners],
        "roles": [{"role": f"{ev.domain}-reader", "access": "read"}]
                 + [{"role": f"{d}-decryptor", "access": "decrypt"} for d in decryptors],
        "authoritativeDefinitions": [
            {"type": "businessDefinition", "url": f"catalog://events/{ev.name}/{ev.version}"},
            {"type": "implementation", "url": "docs/architecture/adr/ADR-012-data-contracts.md"},
        ],
        "customProperties": [
            {"property": "xPiiMax", "value": highest},
            {"property": "eventSchema", "value": str(ev.schema_path.relative_to(cat.root))},
            {"property": "visibility", "value": ev.visibility},
            {"property": "audience", "value": ev.audience},
        ],
    }
    return merge_overlay(contract, ev.overlay, ev.overlay_path)


def merge_overlay(contract: dict, overlay: dict | None, where: Path | None) -> dict:
    """Overlay owns description/SLA/team/terms/support/price/tags; quality and authoritativeDefinitions append;
    customProperties merge by name with the generated value winning. Any other key is a conflict and fails the build."""
    if not overlay:
        return contract
    bad = sorted(set(overlay) - ODCS_OVERLAY_KEYS)
    if bad:
        raise SystemExit(f"{where}: overlay may not set generated keys {bad}; change the event schema instead (data-contracts.md)")
    out = copy.deepcopy(contract)
    for k in ("description", "slaProperties", "team", "terms", "support", "price", "tags"):
        if k in overlay:
            out[k] = overlay[k]
    if "quality" in overlay:
        out["schema"][0]["quality"] = out["schema"][0]["quality"] + list(overlay["quality"])
    if "authoritativeDefinitions" in overlay:
        out["authoritativeDefinitions"] = out["authoritativeDefinitions"] + list(overlay["authoritativeDefinitions"])
    if "customProperties" in overlay:
        gen = {p["property"] for p in out["customProperties"]}
        out["customProperties"] = out["customProperties"] + [p for p in overlay["customProperties"] if p["property"] not in gen]
    return out


def _odcs_logical(physical: str) -> str:
    """ODCS v3.0.2 logicalType enum: string|date|number|integer|object|array|boolean. Timestamps are `date`
    (data-contracts.md's example says `timestamp`, which the ODCS JSON Schema rejects)."""
    if physical.startswith("decimal") or physical == "double":
        return "number"
    if physical == "int64":
        return "integer"
    if physical == "bool":
        return "boolean"
    if physical.startswith("timestamp") or physical == "date32":
        return "date"
    if physical == "struct":
        return "object"
    if physical == "list":
        return "array"
    return "string"


def emit_odcs(cat: Catalog) -> dict[str, str]:
    out: dict[str, str] = {}
    for ev in sorted(cat.events.values(), key=lambda e: e.detail_type):
        if ev.visibility != "public":
            continue
        srcs = [ev.path, ev.schema_path, cat.domains[ev.domain].path] + ref_sources(ev.schema, ev.schema_path.parent)
        if ev.overlay_path:
            srcs.append(ev.overlay_path)
        rel = CATALOG_PREFIX + str((ev.path / "odcs.yaml").relative_to(cat.root))
        _emit(out, rel, "# GENERATED by catalog-gen from schema.json + data-product.yaml. Do not edit; run `task gen`.\n"
              + _y(odcs_contract(cat, ev)), srcs)
    return out


def emit_manifest(cat: Catalog, files: dict[str, str]) -> dict[str, str]:
    order = ["validation", "parquet", "rules/*-public-forward*", "rules/*-fan-out*", "rules/*-consumer-*", "archive", "catalog/events/*/odcs.yaml"]
    manifest = {"order": order, "files": sorted(files), "consumers": consumer_targets(cat),
                "splitRules": sorted(f for f in files if ".part-" in f)}
    PROVENANCE["deploy-order.json"] = sorted(str(p) for p in {d.path for d in cat.domains.values()} | {s.path for s in cat.services.values()})
    return {"deploy-order.json": _j(manifest)}


EMITTERS = [emit_rules, emit_routing_map, emit_validation_bundles, emit_parquet_schemas, emit_odcs]

# ---------------------------------------------------------------- plumbing


def _j(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def _compact(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True)


def _y(obj) -> str:
    return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=120)


def generate(cat: Catalog) -> dict[str, str]:
    PROVENANCE.clear()
    files: dict[str, str] = {}
    for em in EMITTERS:
        for k, v in em(cat).items():
            if k in files:
                raise SystemExit(f"two emitters wrote {k}")
            files[k] = v
    files.update(emit_manifest(cat, files))
    return dict(sorted(files.items()))


def _target(rel: str, out: Path, catalog: Path) -> Path:
    return catalog / rel[len(CATALOG_PREFIX):] if rel.startswith(CATALOG_PREFIX) else out / rel


def on_disk(files_or_out: Path, catalog: Path) -> dict[str, str]:
    out = files_or_out
    found = {str(p.relative_to(out)): p.read_text() for p in out.rglob("*") if p.is_file()} if out.exists() else {}
    for p in catalog.glob("events/**/odcs.yaml"):
        found[CATALOG_PREFIX + str(p.relative_to(catalog))] = p.read_text()
    return found


def write(files: dict[str, str], out: Path, catalog: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for rel in on_disk(out, catalog):
        if rel not in files:
            _target(rel, out, catalog).unlink()
    for p in sorted(out.rglob("*"), reverse=True):
        if p.is_dir() and not any(p.iterdir()):
            p.rmdir()
    for rel, content in files.items():
        p = _target(rel, out, catalog)
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists() or p.read_text() != content:
            p.write_text(content)


def check(files: dict[str, str], out: Path, catalog: Path) -> int:
    disk = on_disk(out, catalog)
    bad = 0
    for rel in sorted(set(files) | set(disk)):
        a, b = disk.get(rel), files.get(rel)
        if a != b:
            bad += 1
            print(f"DRIFT {rel}" + ("  (missing on disk)" if a is None else "  (not generated)" if b is None else ""))
            if a and b:
                sys.stdout.writelines(difflib.unified_diff(a.splitlines(True), b.splitlines(True), "on-disk", "generated"))
    return 1 if bad else 0


def explain(cat: Catalog, files: dict[str, str], rel: str) -> int:
    if rel not in files:
        print(f"{rel}: not generated")
        return 1
    emitter = "emit_manifest"
    for em in EMITTERS:
        PROVENANCE.clear()
        if rel in em(cat):
            emitter = em.__name__
            break
    generate(cat)
    print(rel)
    print(f"  emitter: {emitter}")
    print("  changes when any of these catalog files change:")
    root = cat.root.resolve()
    for s in PROVENANCE.get(rel, []):
        p = Path(s)
        print(f"    {p.relative_to(root) if p.is_relative_to(root) else p}")
    return 0


def main() -> int:
    global PATTERN_LIMIT
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "check", "explain"])
    ap.add_argument("--catalog", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pattern-limit", type=int, default=4096, help="EventBridge pattern size limit in bytes")
    ap.add_argument("path", nargs="?")
    a = ap.parse_args()
    PATTERN_LIMIT = a.pattern_limit
    catalog = a.catalog.resolve()
    cat = load(catalog)
    files = generate(cat)
    if a.cmd == "build":
        write(files, a.out, catalog)
        digest = hashlib.sha256("".join(f"{k}{v}" for k, v in files.items()).encode()).hexdigest()[:12]
        print(f"wrote {len(files)} files to {a.out} (+ {sum(k.startswith(CATALOG_PREFIX) for k in files)} into the catalog) digest {digest}")
        return 0
    if a.cmd == "check":
        return check(files, a.out, catalog)
    if not a.path:
        ap.error("explain needs a generated file path")
    return explain(cat, files, a.path)


if __name__ == "__main__":
    raise SystemExit(main())
