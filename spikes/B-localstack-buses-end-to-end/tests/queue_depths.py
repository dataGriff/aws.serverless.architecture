"""Print the depth of every queue LocalStack knows about. Run: task depths"""
from harness import sqs

for url in sorted(sqs.list_queues().get("QueueUrls", [])):
    a = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=["ApproximateNumberOfMessages",
                                                                "ApproximateNumberOfMessagesNotVisible"])["Attributes"]
    print(f"{url.rsplit('/', 1)[-1]:40} {int(a['ApproximateNumberOfMessages']) + int(a['ApproximateNumberOfMessagesNotVisible'])}")
