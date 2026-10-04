# Spike D — EventBridge Custom Event Bus as the central bus

Follows Spike B's finding that Classic buses deliver one bus-to-bus hop only. Asks: does the Custom Event Bus
(relaunched 2026-09-24, `eventsv2`) give the platform what ADR-001/008/011 were assembling by hand — consumer-owned
subscriptions, retention + replay, FIFO per aggregate, publish-time dedup — and does the Classic domain side survive?

Runs in **eu-west-1** against a real account: there is no LocalStack emulation and no eu-west-2 endpoint yet.
Terraform uses the `awscc` provider (`awscc_eventsv2_event_bus`, `awscc_eventsv2_subscriber`); `hashicorp/aws` has no resources for it.

```sh
aws sso login --profile admin
task apply      # bus (7-day retention) · 6 subscribers · probes · Classic orders-bus bridging into it
task test       # ~5 min; names are the contract
task dlq-peek   # DLQ records with attributes
task send -- events/order-placed.json
task destroy
```

Result and evidence: [findings.md](findings.md).
