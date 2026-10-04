# patterns/  — SPIKE: replaced in spike C

Hand-written EventBridge patterns in exactly the shape the generator will emit.
One file per rule; Terraform reads them with `jsondecode(file(...))`.

| file | lives on | target | purpose |
| --- | --- | --- | --- |
| `{domain}-public-forward` | domain bus | central | only the domain's own public events leave |
| `{domain}-fan-out` | central | domain bus | everything public except the domain's own (`anything-but` + `prefix`) |
| `{domain}-fan-out.enumerated` | central | domain bus | same intent, enumerating the other domains' prefixes — fallback if LocalStack rejects `anything-but` |
| `{domain}-consumer-*` | domain bus | SQS | what `receives[]` would generate |
| `probe-all` | every bus | SQS | test visibility: everything that flowed |
| `broken-target` | central | SQS without a policy | forces the DLQ path |
| `orders-transformer-forward` | orders bus | central | only with `enable_transformer_rule=true`; verifies input transformers on bus targets |
