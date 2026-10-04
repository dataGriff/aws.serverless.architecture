"""Archive shim (ADR-024): one EventBridge event in, one JSON object out, Hive-partitioned so DuckDB can read it.

    ok    s3://<domain bronze>/raw/source=<source>/detail_type=<detail-type>/<id>.json
    fail  s3://<domain bronze or fallback>/processing-failed/reason=<reason>/source=.../detail_type=.../<id>.json

The bucket comes from the generated routing map (source prefix -> bucket); the verdict from validate.classify
over the generated validation bundles packaged under validation/. Inside LocalStack's Lambda containers
AWS_ENDPOINT_URL is injected, so a default boto3 client reaches LocalStack's S3.
"""
import json
import os
from pathlib import Path

import boto3

from validate import classify, load_bundles

s3 = boto3.client("s3")
ROUTING_MAP = json.loads(os.environ["ROUTING_MAP"])
FALLBACK_BUCKET = os.environ["FALLBACK_BUCKET"]
BUNDLES = load_bundles(Path(__file__).parent / "validation")


def bucket_for(source: str) -> str:
    for prefix, route in ROUTING_MAP.items():
        if source.startswith(prefix):
            return route["bucket"]
    return FALLBACK_BUCKET


def handler(event, _context):
    verdict = classify(event, BUNDLES)
    partition = f"source={event['source']}/detail_type={event['detail-type']}/{event['id']}.json"
    if verdict is None:
        key, metadata = f"raw/{partition}", {}
    else:
        reason, message = verdict
        key, metadata = f"processing-failed/reason={reason}/{partition}", {"reason": reason, "message": message[:1024]}
    bucket = bucket_for(event["source"])
    s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(event).encode(), ContentType="application/json", Metadata=metadata)
    return {"bucket": bucket, "key": key, "verdict": verdict}
