---
id: payment-service
name: Payment service
version: 1.0.0
domain: payments
sends:
  - id: PaymentCaptured
    version: 1
receives:
  - id: OrderPlaced
    version: 1
---
