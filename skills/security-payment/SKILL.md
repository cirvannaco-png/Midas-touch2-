---
name: security-payment
description: Audit Medis Touch payment integrity, copy-key security, entitlement and authorization boundaries.
metadata:
  slash-command: enabled
---

# Security and Payment Specialist

Audit payment adapters and copy authorization fail-closed.

Verify:
- cryptographic webhook/request verification;
- transaction reconciliation against expected identity, amount, currency, plan and transaction ID;
- idempotency and terminal-event handling;
- copy-key fingerprinting/constant-time verification, rotation, revocation, last-use tracking and rate limiting;
- no secrets in logs;
- no broker credentials in the bridge.

If a provider contract is undocumented or unverified, mark it BLOCKED rather than guessing.
