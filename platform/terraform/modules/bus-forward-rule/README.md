# bus-forward-rule

A rule on one bus whose target is another bus: the domain's generated **public-forward** rule, the one bus-to-bus hop AWS allows (ADR-021). The pattern is `generated/rules/{domain}-public-forward[.part-N].json`, never hand-written. Every target has a role and a DLQ.

| Input | Type | Default | Meaning |
| --- | --- | --- | --- |
| `name` | string | required | Rule name |
| `source_bus_name` | string | required | The bus the rule sits on (the domain bus) |
| `target_bus_arn` | string | required | The bus it forwards to (central) |
| `event_pattern` | any | required | The generated pattern as a map; the module JSON-encodes it. The generator splits it below 4 KB |
| `input_transformer` | object | `null` | Kept for the single-account LocalStack env only. **AWS rejects input transformers on bus targets** ("Modifying the input for target … is not supported", Spike B), which is why ADR-022 supersedes ADR-006; the licensed LocalStack image rejects it too |
| `tags` | map(string) | `{}` | |

| Output | |
| --- | --- |
| `rule_arn` | |
| `dlq_url` | the target's dead-letter queue; `THIRD_ACCOUNT_HOP_DETECTED` and `LOOP_DETECTED` land here on AWS |

LocalStack: the hop is delivered. **Hop limits and loop detection are sandbox-only**: LocalStack delivers a second bus-to-bus hop that AWS refuses (Spike B, the finding behind ADR-021). DLQ records are sandbox-only on Community.
