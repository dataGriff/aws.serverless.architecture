# Accepted trade-offs

Written down so nobody rediscovers them. Each is a consequence of a row in `decisions.md`.

## Delivery semantics

- No ordering and no exactly-once anywhere. Every consumer handles out-of-order and duplicates; silver reconstructs order via `aggregateVersion`.
- Fan-out-all means every domain bus receives every public event; cost is N× deliveries and no per-event access control until `audience: restricted` is used.
- London's default EventBridge quotas are lower than Virginia's; each event counts twice plus one invocation per domain. Checked on day one, raised before step 4.

## Freshness & analytics

- Analytics are batch: nothing fresher than ~2–3 h without the Firehose-to-Parquet or Athena triggers.
- Analysts without DuckDB tooling have no SQL console until Athena is switched on.
- Bronze holds public events only; internal history lives in each domain's 30-day archive.

## Testing & environments

- Automated tests never see two domains together; behavioural mismatches surface in `test` UAT, production smokes and canaries, not CI.
- LocalStack is a proxy; pattern matching, transformers and cross-account behaviour differ. The nightly sandbox run is the safety net.
- Prism proves shape, not behaviour; Schemathesis proves conformance, not correctness.

## PII controls

- Encrypting `direct` fields puts a key fetch on the publish path; cached per-subject data keys with a short TTL keep it to microseconds, at the cost of a cache to invalidate on erasure.
- Consumers need the shared crypto library and an approved decryptor role; a consumer that persists decrypted data owns its own erasure path, triggered by `SubjectErased`.
- Analytics is blind to `direct` fields by design; reversible tokenisation is the exception path, with a DPIA entry.
- Crypto-shredding is irreversible: key deletion needs an approval step and a short grace period, and a shredded key makes historical replays of that subject decode as "erased".

## Control plane

- One catalog repo is one control plane: coherence in exchange for merge contention and generator blast radius. Semver pins, canary apply order and CODEOWNERS mitigate; federation is the escape hatch.
- The generator is bespoke platform software with a bus factor; snapshot tests and a two-person ownership rule are the minimum.
- Everything is generated, so debugging goes through generated code and `generated/` must stay reviewable.
- ODCS adds one more artefact per event version; generating it removes drift but ties you to the tooling's maturity (datacontract-cli, ODCS v3).
