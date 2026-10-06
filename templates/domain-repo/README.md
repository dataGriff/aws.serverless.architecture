# Domain repository template

The starting point for a domain's own repository: its service code, its Terraform env for domain-local testing, and the L0 and L1 suites that prove its events and its API with no other domain present (ADR-025, `docs/architecture/testing.md`). Prompt 14 (onboard a domain) says "domain repo from the template"; this is it.

What is real today and what is a skeleton:

| Part | State |
| --- | --- |
| `Taskfile.yml`, `.mise.toml`, `docker-compose*.yml`, `pins.yaml` | real: the toolchain, licensed LocalStack with `ENFORCE_IAM=1`, and the three pins (catalog tag, platform tag, LocalStack image) |
| `tests/test_l0_contract.py` | real: every example the catalog ships for this domain's events validates against the generated validation bundle (envelope flattened in, `direct` fields as ciphertext when public). Runs with no infrastructure. |
| `tests/test_l1_events.py`, `tests/test_l1_api.py` | skeletons carrying the step-1 test names from prompt 03, each marked `skip` with the reason. The names are the acceptance criteria; keep them. |
| `tests/conftest.py` | fixtures wired to `platform_testing`; the LocalStack and Terraform fixtures assume `task apply` ran |
| `terraform/envs/local/` | empty on purpose: step 1 (prompt 03) writes it from `platform/terraform/modules`, and step 3 replaces most of it with the pinned `platform-local` module. The proven shape for one domain plus a stub central is `spikes/B-localstack-buses-end-to-end/terraform/envs/local/main.tf`. |
| `src/` | the service: outbox, handlers, the generated client of any upstream API. Prompt 03 fills it. |

## Lifting it into its own repository

1. Copy this directory to the new repository root.
2. `pins.yaml`: set the catalog tag, the platform tag and the LocalStack image. The Taskfile checks out the catalog at that tag under `.catalog/` and expects the platform tooling at the path `PLATFORM` names (a submodule at `platform/` is simplest).
3. Rename `sample` in `Taskfile.yml` (`DOMAIN`) and in the tests to your domain.
4. `mise install && task up && task gen && task test:l0` should be green before any infrastructure exists.
5. Then `/arch:step-1-walking-skeleton` for the first domain, or `/arch:onboard-a-new-domain` for later ones.

Never depend on another domain's code or a shared environment: upstream APIs are Prism mocks of their catalog specs at the pinned tag (`task mock`), and the central bus is the Classic stub in `platform-local`.
