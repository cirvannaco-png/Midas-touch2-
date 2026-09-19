# Midas Touch Decision / Research Certification

## Integrated strategy state

MR !9 (regime-first peer strategy routing) and MR !10 (multi-asset temporal research and outcome provenance) are treated as one strategy/research state for validation. The integration branch is integration/strategy-research-parity-20260918.

The integrated state is **not** production-certified by being mergeable. It must survive the same compile, replay, backtest, OOS and forward-evidence sequence.

## Decision fingerprint

The authoritative decision contract is:

canonical decision fields
→ fixed-order canonical serialization
→ SHA-256
→ decision_fingerprint

The fingerprint-bearing envelope crosses the EA, signal publisher, backend/API and database. Telegram receives the same fingerprint from the persisted envelope.

The backend recomputes the fingerprint. A mismatch is persisted as PARITY_MISMATCH and the signal is not queued for delivery.

Rollout compatibility is controlled by REQUIRE_DECISION_FINGERPRINT. It defaults to false so legacy EA builds can be observed during transition: missing fingerprints are recorded as FINGERPRINT_MISSING and remain eligible for delivery, but they are never eligible for locked-OOS certification. After the fingerprint-capable EA binary is compiled, validated and deployed, strict mode should be enabled so missing fingerprints become a hard acceptance failure.

## Replay determinism

The replay engine accepts the original immutable decision context and a deterministic decision function. Expected result:

original_fingerprint == replayed_fingerprint

A difference emits REPLAY_NON_DETERMINISM and records the changed fields. The replay contract is designed to expose hidden state, time dependence, default drift, strategy-selection drift, feature differences and incomplete inputs.

## OOS purity

Locked OOS evaluation is only eligible after the provenance firewall passes. At minimum the record has:

- signal time
- decision time
- execution time when filled
- outcome time when resolved
- server data-received time
- strategy/model/weight/calibration/feature/environment versions
- decision fingerprint and canonical decision
- parity status
- strategy, symbol and asset classification
- complete execution-cost fields for filled trades

The temporal invariant is strict:

training_max_signal_time < validation_min_signal_time < holdout_min_signal_time

A certification run rejects future timestamps, duplicate decisions, mixed sources, missing lineage, altered canonical decisions, parity failures, unknown versions/classification, and incomplete cost provenance.

## Research / optimization separation

The pipeline is:

TRAIN → VALIDATION → LOCKED OOS

Locked OOS is not a tuning set. Any change to thresholds, strategy weights, ATR multipliers, regime rules, risk parameters, calibration or feature logic creates a new model/version lineage. The previous OOS evidence is not reused as if it were untouched evidence for the new version.

## Champion / challenger

A strategy can only enter promotion review after locked-OOS qualification. Evidence includes minimum sample size, OOS statistics, confidence intervals, drawdown, stability across regimes and robustness to execution costs. One favorable backtest is not sufficient evidence.

## Daily trade target

The EA carries a default minimum qualified-trade target of 3 per day.

This is deliberately a target/telemetry rule, not a forced-trading rule. It never lowers confidence thresholds, disables news locks, bypasses risk controls or creates synthetic trades merely to hit three. A day with fewer than three qualified executions is recorded as an under-target day.

This distinction is essential: frequency is an operational objective; trade admission remains governed by the strategy and risk system.

## Latency architecture

The existing T0–T7 latency trace remains authoritative for execution timing. Stage budgets are recorded rather than silently tolerated.

For the signal-delivery path, the EA/backend decision acceptance no longer needs to wait for Telegram delivery. The backend persists the signal and a durable outbox entry, returns queued, and a background worker performs Telegram delivery with bounded retries. A worker interruption can recover leased work from the outbox.

The latency objective is therefore:

EA decision
→ fingerprint
→ backend parity check
→ durable database commit
→ immediate acknowledgement

rather than:

EA decision
→ backend
→ database
→ Telegram API/retries
→ final acknowledgement

## Certification artifact

A completed certification artifact links:

Git commit
→ EA source/binary
→ decision schema
→ strategy/model/config versions
→ dataset identity
→ training/validation/OOS configuration
→ results/costs
→ parity result
→ replay result
→ temporal/provenance result
→ certificate hash

Possible final states are:

- PASS
- FAIL
- INSUFFICIENT_EVIDENCE

PASS requires the required integrity gates plus sufficient locked-OOS evidence. The certificate itself is SHA-256 hashed.
