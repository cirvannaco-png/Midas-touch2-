---
name: ci-deployment
description: Validate Medis Touch GitLab CI, deployment configuration and release readiness without changing trading behavior.
metadata:
  slash-command: enabled
---

# CI and Deployment Guardian

Validate GitLab CI syntax, MQL5 structural validation, Python tests/security checks, Telegram bridge tests, and deployment configuration.

Treat GitLab as the source of truth for this migration.
Do not destroy the existing Render service until a GitLab-backed replacement is independently verified healthy.
Do not expose or reproduce secret values.
A green pipeline proves CI validation only; it does not prove MetaEditor compilation, live broker execution, payment production readiness, or live-money safety.
