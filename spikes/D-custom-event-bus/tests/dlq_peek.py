"""Every DLQ record with its attributes (left in place). Run: task dlq-peek"""
import json
import re

from harness import DLQ, sqs

mask = lambda s: re.sub(r"[0-9]{8}([0-9]{4})", r"********\1", s)  # noqa: E731

for name, url in DLQ.items():
    r = sqs.receive_message(QueueUrl=url, MaxNumberOfMessages=10, MessageAttributeNames=["All"], VisibilityTimeout=0)
    for m in r.get("Messages", []):
        attrs = {k: v.get("StringValue") for k, v in (m.get("MessageAttributes") or {}).items()}
        print(mask(json.dumps({"dlq": name, "attrs": attrs, "body": m["Body"][:600]})))
