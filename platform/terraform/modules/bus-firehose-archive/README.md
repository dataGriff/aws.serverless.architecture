# bus-firehose-archive

The **AWS-shaped archive** (ADR-024): a rule on a bus → Kinesis Data Firehose → S3 bronze, with the same validation function as the shim (`src/validator.py`, calling `validate.py`'s `classify`) as the stream's transform, dynamic partitioning on `source` / `detail-type`, 60 s buffers and a `processing-failed/` error prefix. On AWS this becomes a Firehose **subscriber** on the Custom Event Bus per domain (step 2 renders it); the Classic-rule form here is what a single account can run.

| Input | Type | Default | Meaning |
| --- | --- | --- | --- |
| `name` | string | required | |
| `bus_name` | string | required | |
| `event_pattern` | any | required | |
| `tags` | map(string) | `{}` | |

| Output | |
| --- | --- |
| `bucket` | the bronze bucket |
| `stream` | the delivery stream name |
| `dlq_url` | the rule target's DLQ |

LocalStack: applies, and that is all it proves. **Dynamic partitioning, the transform contract and `ErrorOutputPrefix` are ignored on both editions** (Spike B's `task probe-firehose`): records land unpartitioned and nothing is quarantined. Everything about this module is sandbox-only (ADR-025); locally, `bus-s3-archiver` stands in with identical validation.
