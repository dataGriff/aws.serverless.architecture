---
id: order-service
name: Order service
version: 1.0.0
domain: orders
sends:
  - id: OrderPlaced
    version: 1
  - id: order.aggregate.updated
    version: 1
receives:
  - id: PaymentCaptured
    version: 1
---
