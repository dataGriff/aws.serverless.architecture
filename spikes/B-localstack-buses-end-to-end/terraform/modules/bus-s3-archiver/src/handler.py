"""Raw archiver: one EventBridge event in, one JSON object out, Hive-partitioned so DuckDB can read it.

Inside LocalStack's Lambda containers AWS_ENDPOINT_URL is injected, so a default boto3 client reaches LocalStack's S3.
"""
import json
import os

import boto3

s3 = boto3.client("s3")
BUCKET = os.environ["BUCKET"]


def handler(event, _context):
    key = f"raw/source={event['source']}/detail_type={event['detail-type']}/{event['id']}.json"
    s3.put_object(Bucket=BUCKET, Key=key, Body=json.dumps(event).encode(), ContentType="application/json")
    return {"bucket": BUCKET, "key": key}
