---
name: phase-b-api
description: Safely decompose Medis Touch API routes into service boundaries without changing behavior.
metadata:
  slash-command: enabled
---

# Phase B API Specialist

Audit `telegram-bridge/app/api/` and route compatibility.

Target boundaries include signals, trades, outcomes, webhook and admin concerns.
Do not duplicate business logic. Extract by delegation only where behavior can be proven unchanged.
Preserve request/response schemas, authentication, idempotency, status codes and error semantics.
For every extraction, add regression coverage before moving further.
Never compress or rewrite an entire route file for a narrow extraction.
