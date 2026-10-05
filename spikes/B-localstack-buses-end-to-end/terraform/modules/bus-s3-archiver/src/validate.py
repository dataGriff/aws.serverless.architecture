"""The validation step of the archive, written once (ADR-024): the Lambda shim calls it locally, a Firehose
transform calls it on AWS. Input: the catalog-generated validation bundles (generated/validation/*.json).

classify(event, bundles) -> None when the event is a conformant public event, else (reason, message):
    unknown-event  no bundle entry for (source, detail-type): not a public event of a known domain
    pii-in-clear   a `direct` field is not a ciphertext envelope {enc, kid, ct}
    schema         detail does not match the generated envelope+payload schema
"""
from __future__ import annotations

import json
from pathlib import Path

import fastjsonschema


def load_bundles(folder: Path) -> dict[str, dict]:
    """detail-type -> {source, schema, ciphertextFields, validate}. Bundles are per domain; detail-types are unique."""
    out: dict[str, dict] = {}
    for f in sorted(folder.glob("*.json")):
        for detail_type, entry in json.loads(f.read_text()).items():
            out[detail_type] = {**entry, "validate": fastjsonschema.compile(entry["schema"])}
    return out


_ABSENT = object()


def _get(detail: dict, dotted: str):
    """Value at a dotted path, or _ABSENT when any segment is missing (absence is the schema's business)."""
    cur = detail
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return _ABSENT
        cur = cur[part]
    return cur


def is_ciphertext(value) -> bool:
    return isinstance(value, dict) and {"enc", "kid", "ct"} <= set(value)


def classify(event: dict, bundles: dict[str, dict]) -> tuple[str, str] | None:
    entry = bundles.get(event.get("detail-type"))
    if entry is None or entry["source"] != event.get("source"):
        return "unknown-event", f"{event.get('source')} {event.get('detail-type')} is not a public event in the catalog"
    detail = event.get("detail")
    if not isinstance(detail, dict):
        return "schema", "detail is not an object"
    for field in entry["ciphertextFields"]:
        value = _get(detail, field)
        if value is not _ABSENT and not is_ciphertext(value):
            return "pii-in-clear", f"{field} is classified direct and is not a ciphertext envelope"
    try:
        entry["validate"](detail)
    except fastjsonschema.JsonSchemaException as e:
        return "schema", e.message
    return None
