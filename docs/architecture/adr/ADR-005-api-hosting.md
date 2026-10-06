---
id: ADR-005
title: "API hosting"
concern: "API hosting"
decision: >-
  **REST API** (regional) per domain in the domain account, deployed from the catalog spec: request validation at the gateway from the same schemas, WAF attachable, usage plans for partners, resource policies. **WAF on day one for anything externally reachable** (PSP webhooks). `{domain}.api.example.com` delegated to the domain; JWT for users, IAM SigV4 for services, issuer owned by the platform. No central gateway; the catalog is discovery.
status: accepted
date: 2026-10-04
reviewed: changed-after-review
revisit_when:
  - "HTTP API only if you move validation into handlers and accept no WAF"
  - "Single hostname or edge caching → CloudFront edge in the platform account"
  - "Private-only → VPC link"
  - "Internal throughput → gRPC/ALB"
  - "BFF → GraphQL in the consuming domain"
---

# ADR-005 · API hosting

## Decision

**REST API** (regional) per domain in the domain account, deployed from the catalog spec: request validation at the gateway from the same schemas, WAF attachable, usage plans for partners, resource policies. **WAF on day one for anything externally reachable** (PSP webhooks). `{domain}.api.example.com` delegated to the domain; JWT for users, IAM SigV4 for services, issuer owned by the platform. No central gateway; the catalog is discovery.

## Revisit only when

HTTP API only if you move validation into handlers and accept no WAF. Single hostname or edge caching → CloudFront edge in the platform account. Private-only → VPC link. Internal throughput → gRPC/ALB. BFF → GraphQL in the consuming domain.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Set its `concern:`, `decision:` and `revisit_when` and run `task adr:build` in the same PR. Generated IaC follows the catalog, never the other way round.
