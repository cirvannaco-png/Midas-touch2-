---
name: ci-deployment
description: Validate Midas Touch GitHub Actions CI, optional GitLab mirroring, deployment configuration and release readiness without changing trading behavior.
metadata:
  slash-command: enabled
---

# CI and Deployment Guardian

Treat GitHub repository `cirvannaco-png/Midas-touch2-`, branch `main`, as the canonical source of truth. Validate the applicable GitHub Actions checks, MQL5 structural validation, Python tests/security checks, Telegram bridge tests, and deployment configuration. GitLab is an optional source-tree mirror; do not treat its branch or pipeline status as canonical evidence.

Do not make GitLab-only source changes. Do not declare mirror parity without `SYNC_VERIFIED` for the current GitHub SHA and independent content verification. Do not create duplicate production schedules or expose/reproduce secret values.

Do not destroy, repoint, or duplicate an existing Render service until its actual provider, deployed commit, database boundary and health have been independently checked and a separate deployment change approved. Repository CI is not a substitute for service/runtime validation.

A green pipeline proves only the checks that actually ran. It does not by itself prove a persisted recalibration cycle, MetaEditor/MT5 Strategy Tester profitability, live broker execution, payment production readiness, or live-money safety.
