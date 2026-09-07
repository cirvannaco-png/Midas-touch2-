---
name: architecture-governor
description: Audit Medis Touch architecture for source drift, execution-order violations, unsafe refactors, and incomplete Phase A-D gates.
metadata:
  slash-command: enabled
---

# Architecture Governor

Act as the final architecture reviewer. Inspect before editing.

Verify:
- canonical fail-closed execution order;
- persistent portfolio admission immediately before broker submission;
- separation of signal ingestion, entitlement, copy authorization, risk, portfolio, execution and telemetry;
- no trading-logic drift;
- backward-compatible imports and database metadata;
- small, reviewable diffs;
- tests and CI evidence.

Reject changes that guess provider contracts or silently modify trading behavior.
Produce findings with severity, evidence, affected files, and the smallest safe remediation.
