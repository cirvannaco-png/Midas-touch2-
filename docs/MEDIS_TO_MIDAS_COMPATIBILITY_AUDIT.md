## Scope
Compatibility-first audit of Medis Touch → Midas Touch 2. This PR contains only a migration review artifact; it does not replace EA execution/recovery code.

## Confirmed comparisons
- `EA/includes/Execution/TradeStateMachine.mqh`: source and target blob SHA both `4f89105d1c9dd4e1879bb3010e0792f4b4293354`; no copy needed.
- `EA/includes/Recovery/RecoveryEngine.mqh`: differs (source SHA `fdfac21c51147a5e82d0e42331ef2b81da640d77`, target SHA `149ed664e862408bfabfbedc418a8c8f2686ced7`). Target adds `OutcomeTrackerLive` integration and trade-identity/leg parsing; preserve target and review semantics before any selective port.
- `tools/gating.py`: differs. Source describes persistence and contradiction handling; target explicitly fails closed when required metrics are indeterminate and gates win rate, confidence AUC, and confidence-to-realized-R correlation. Do not replace target wholesale.
- `tools/metrics_engine.py`: differs in implementation detail; both separate coverage from expectancy. Compare complete functions/tests before deciding whether any source-only behavior is needed.

## Gate before merge
Run the repository's Python test suite and MQL5 structural validation; compile the EA in MetaEditor and exercise Strategy Tester/demo scenarios before considering execution-path changes. This PR is not evidence of successful compilation, profitability, or live readiness.