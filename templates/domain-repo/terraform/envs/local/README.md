# terraform/envs/local

Empty on purpose. Step 1 (`/arch:step-1-walking-skeleton`) writes this env from `platform/terraform/modules`: the
domain's Classic bus, the generated public-forward rule, consumer rules from `receives[]`, a Classic stub central with
subscriber-shaped rules targeting this domain's own queues, and the archive shim into the domain's bronze bucket, all
read from `generated/local` (`-var generated_dir=…`). Step 3 replaces most of it with the pinned `platform-local` module.

The proven shape, for two domains, is `spikes/B-localstack-buses-end-to-end/terraform/envs/local/main.tf` in the
platform repo: copy the provider block, the `generated_dir` variable and the `fileset()` loops, keep one domain.
