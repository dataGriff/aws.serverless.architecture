"""Print every DLQ record with EventBridge's error attributes (messages are left in place).
Run: task dlq-peek  /  task sandbox-dlq-peek"""
import json
import re

from harness import dlqs, sqs

mask = lambda s: re.sub(r"[0-9]{8}([0-9]{4})", r"********\1", s)  # noqa: E731

for rule, url in dlqs().items():
    r = sqs.receive_message(QueueUrl=url, MaxNumberOfMessages=10, MessageAttributeNames=["All"], VisibilityTimeout=0)
    for m in r.get("Messages", []):
        attrs = {k: v.get("StringValue") for k, v in (m.get("MessageAttributes") or {}).items()}
        b = json.loads(m["Body"])
        print(mask(json.dumps({"dlq": rule, "ERROR_CODE": attrs.get("ERROR_CODE"), "ERROR_MESSAGE": attrs.get("ERROR_MESSAGE"),
                               "source": b.get("source"), "detail-type": b.get("detail-type"),
                               "eventId": b.get("detail", {}).get("eventId"), "bus_event_id": b.get("id")})))
