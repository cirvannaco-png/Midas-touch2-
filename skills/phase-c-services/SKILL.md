---
name: phase-c-services
description: Extract Medis Touch application services for payments, subscriptions, copy authorization, risk and execution boundaries.
metadata:
  slash-command: enabled
---

# Phase C Service Specialist

Map existing service behavior before changing it.

Enforce:
- verified payment -> reconciled transaction -> subscription -> entitlement;
- entitlement plus explicit copy authorization before copy feed access;
- user risk requests are rejected when above the system maximum, never silently reduced;
- authoritative persistent portfolio admission is required before execution;
- failure of any mandatory gate stops the operation.

Provider-specific payment behavior must remain in provider adapters. Never invent an API field, endpoint, signature algorithm or webhook contract.
