# MIDAS TOUCH — Development → Production Promotion

## 1. Development

Create a branch from `main`.

Examples:
- `feature/regime-calibration-v2`
- `fix/riskguard-persistence`
- `audit/fvg-timeframe-integrity`

Keep the change narrowly scoped and auditable.

## 2. Review

Open a PR on GitHub and/or MR on GitLab.

The integration request should state:
- problem
- proposed change
- affected components
- risk impact
- test evidence
- rollback method

Conflicts are resolved explicitly; they are never auto-resolved by the cross-provider synchronizer.

## 3. Integration into main

Merge only after the review and required validation are complete.

`main` represents the current integration candidate.

## 4. Validation gate

Before promotion, record evidence for the commit being released:

### Code correctness
- MQL5 EA compiles without errors.
- No known compiler blockers remain.
- Static analysis/audit is clean for release-critical paths.

### System parity
- Backend trade/rule contracts match EA expectations.
- TradeSetup fields and invalidation semantics remain consistent.
- Indicator calculations use the intended timeframe/source data.
- Configuration hashes/version identifiers are synchronized.

### Risk controls
- Position sizing limits are enforced.
- RiskGuard state is persistent only where intended and scoped correctly.
- News lock works before/after configured high-impact events.
- Spread/volatility guards work.
- Broker minimum-distance/freeze rules are respected.
- DynamicStopEngine only tightens risk and obeys the defined R-multiples.
- Stop-loss and setup invalidation remain distinct concepts.

### Strategy/recalibration
- Regime detection is wired into scoring.
- Strategy selection is deterministic and auditable.
- Recalibration follows Challenger → evaluation → approval → Champion → hash → EA ACK → Active → rollback.
- No unapproved model/config becomes active.

### Evidence
- Reproducible backtest artifacts are stored.
- Backend/EA parity checks are recorded.
- Controlled forward-test evidence is available.
- Critical audit findings are closed or explicitly waived by the release owner.

## 5. Production bootstrap

The SHA-1 `midas-touch2-sync` repository is a transport staging surface and is not a production promotion target. Production promotion must establish the release state independently in the active GitHub and active GitLab engineering repositories.

The production boundary is **not currently bootstrapped on both providers**.

As of the 2026-09-18 pre-protection audit:

- GitHub `production` exists at `74cabb8d61564c1bebec2287df6ad44f82dea2aa` and is 18 commits behind GitHub `main`.
- GitLab `production` does not exist.
- GitHub and GitLab use different Git object formats, so a literal SHA comparison across providers is invalid.

For the first valid production bootstrap, use this procedure:

1. Verify the intended release source tree on GitHub and GitLab is identical using provider-specific commit IDs and tree/content verification.
2. Identify the exact validated release commit on the provider where the release is prepared.
3. Create `production` from that exact release source tree on both providers.
4. Verify each provider's `production` ref resolves to the recorded release state and that the source trees are identical across providers.
5. Apply the protected/ref-rule configuration before normal release use.
6. Record the provider-specific production commit IDs and the cross-provider tree verification evidence.

Do not promote the existing GitHub `production` ref merely because it exists; it is stale relative to the current `main`.

## 6. Promotion

Promote the exact validated `main` release state to `production`.

Promotion must verify:
1. GitHub `main` and GitLab `main` represent the same intended source tree/release state using provider-specific commit IDs.
2. GitHub `production` and GitLab `production` exist and represent that same intended release state.
3. On each provider, `production` is an ancestor of that provider's `main`.
4. The provider-specific release commit IDs and cross-provider source-tree verification evidence are recorded.

If any verification fails, STOP.

## 7. Forward test

Use the production release candidate in a controlled environment first.

Observe:
- execution parity
- slippage/spread behavior
- broker constraints
- news-lock behavior
- stop management
- error/exception rates
- telemetry and audit logs

Forward-test success is evidence, not a guarantee of future trading performance.

## 8. Live rollout

Only after the controlled forward-test gate is satisfied should live deployment be considered.

Rollout should be staged:
- demo
- smallest controlled live exposure
- monitored expansion

A software promotion does not itself authorize capital deployment.

## Rollback

### Preferred rollback: revert-and-repromote

For a normal incident:

1. Freeze further promotion.
2. Identify the faulty release and affected commits.
3. Create a dedicated rollback/fix branch from current `main`.
4. Revert the faulty change(s) rather than rewriting history.
5. Run the same compile, audit, parity, backtest, and controlled-forward-test gates.
6. Merge the validated rollback fix into `main`.
7. Promote that exact new `main` commit to `production`.
8. Mirror the exact release commit to both providers and record the incident evidence.

This is the default because it preserves an auditable history.

### Emergency exact-release restoration

If an incident requires the production ref itself to point immediately to a previously validated commit:

- Stop all automatic synchronization.
- Record the provider-specific target commit IDs and incident/change-approval identifier.
- The release owner/admin must explicitly authorize the protected-ref reset on **both** providers.
- Use a lease-checked, audited non-fast-forward update on each provider; never use an unqualified force-push.
- Verify both `production` refs resolve to their recorded target commits and that the source trees match before resuming operations.
- The cross-provider sync controller must never perform this operation automatically.

This emergency path is exceptional and requires provider-level protection bypass/admin authority. It must never be used to conceal an unreviewed release.
