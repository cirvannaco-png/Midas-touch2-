# Incremental Extraction Policy

Medis Touch has a deliberately large compatibility surface. Route and model decomposition must therefore be performed with narrow, reviewable changes.

## Rule

Never replace a consolidated production module wholesale when extracting one boundary.

For each extraction:

1. map imports and side effects
2. add the target module
3. add characterization/regression tests
4. move one coherent behavior boundary
5. preserve the legacy public import/API surface
6. run the full GitLab pipeline
7. inspect the diff for accidental deletions

## Phase B

Extract one router family at a time from `app/routes.py`: signals, trades, outcomes, webhook, then admin. Endpoint paths, methods, dependencies, response schemas, status codes, and side effects are compatibility contracts.

## Phase C

Route handlers should become thin orchestration layers over application services. Services must own business invariants without duplicating trading logic.

## Phase D

Split `app/models.py` only after import and migration dependencies are mapped. Keep `app.models` as a compatibility re-export until all consumers are migrated. `Base.metadata`, table names, column names, and PostgreSQL enum behavior are non-negotiable.

## Trading logic

No Phase B/C/D extraction is permitted to alter MQL5 strategy selection, indicator parameters, confidence thresholds, risk calculations, news filtering, broker execution, or signal semantics.
