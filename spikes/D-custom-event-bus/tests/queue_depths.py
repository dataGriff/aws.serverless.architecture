"""Depth of every spike queue. Run: task depths"""
from harness import DLQ, Q, sqs

for name, url in sorted({**Q, **{f"dlq:{k}": v for k, v in DLQ.items()}}.items()):
    a = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=["ApproximateNumberOfMessages",
                                                                "ApproximateNumberOfMessagesNotVisible"])["Attributes"]
    print(f"{name:42} {int(a['ApproximateNumberOfMessages']) + int(a['ApproximateNumberOfMessagesNotVisible'])}")
