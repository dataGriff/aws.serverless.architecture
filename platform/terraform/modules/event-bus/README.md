# event-bus

An EventBridge **Classic** bus with its resource policy. Every domain's bus (`{domain}-bus`) and the Classic stub central that `platform-local` uses (ADR-021, ADR-025). The real central is a Custom Event Bus and is not this module (step 2 adds `custom-event-bus` on `awscc`, with Spike D's resource shapes).

| Input | Type | Default | Meaning |
| --- | --- | --- | --- |
| `name` | string | required | Bus name, `orders-bus` or `central-bus` |
| `put_events_principals` | list(string) | `[]` | Account ids or role ARNs allowed to `PutEvents`. Empty: no cross-account policy. Since ADR-021 a domain bus carries none (nothing outside the account publishes to it); the stub central lists the forward rules' roles |
| `tags` | map(string) | `{}` | |

| Output | |
| --- | --- |
| `name`, `arn` | the bus |

LocalStack: bus and policy are created, but **resource-policy enforcement is sandbox-only** (Spike B: LocalStack Community never denies; the licensed image with `ENFORCE_IAM=1` evaluates IAM but not bus policies). A wrong principal list is found in the real sandbox (ADR-025).
