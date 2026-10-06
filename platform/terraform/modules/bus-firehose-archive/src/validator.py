"""Firehose transform in the shape ADR-009 describes: validate each record, quarantine failures,
return partition keys so dynamic partitioning can lay bronze out by source / detail-type.

Validation here is the minimum that makes the probe meaningful: an eventId must exist, and a
`direct`-classified field (customerEmail) must not arrive in clear (ciphertext is marked `enc:`).
"""
import base64
import json


def handler(event, _context):
    print("INVOCATION SHAPE:", json.dumps(event)[:600])
    out = []
    for i, r in enumerate(event["records"]):
        # AWS always sends recordId; LocalStack 4.14 / 2026.9 send only {"data": ...}, so fall back to the index
        r.setdefault("recordId", str(i))
        try:
            e = json.loads(base64.b64decode(r["data"]))
            d = e.get("detail") or {}
            if "eventId" not in d:
                raise ValueError("missing eventId")
            v = d.get("customerEmail")
            if isinstance(v, str) and not v.startswith("enc:"):
                raise ValueError("direct PII in clear: customerEmail")
            out.append({"recordId": r["recordId"], "result": "Ok",
                        "data": base64.b64encode((json.dumps(e) + "\n").encode()).decode(),
                        "metadata": {"partitionKeys": {"source": e["source"], "detail_type": e["detail-type"]}}})
        except Exception:  # noqa: BLE001 — any failure is a quarantine, by design
            out.append({"recordId": r["recordId"], "result": "ProcessingFailed", "data": r["data"]})
    return {"records": out}
