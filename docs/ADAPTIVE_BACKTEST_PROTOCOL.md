# Adaptive Backtest / Self-Test Protocol

## Online learning inside a chronological Strategy Tester run

Midas can evaluate its own historical evidence while a backtest is running:

```text
historical bars
    -> regime/environment snapshot
    -> eligible strategies
    -> environment-history adjustment (only if statistically qualified)
    -> strategy selection
    -> setup/risk/execution gates
    -> Strategy Tester fill/outcome
    -> Environment -> Strategy -> Outcome memory
    -> statistics
    -> next eligible decision
```

The memory is updated **after** an outcome resolves. A future decision may use
only outcomes whose timestamps precede that decision. This is online learning,
not a look-ahead optimization.

## Evidence controls

- Minimum resolved sample per environment/strategy cell: 30 by default.
- A positive adjustment requires positive expectancy, profit factor > 1 and a
  95% Wilson lower bound >= 50% win rate.
- A negative adjustment requires twice the minimum sample plus negative
  expectancy, profit factor < 1 and a 95% Wilson upper bound < 50%.
- Historical adjustment is bounded and does not bypass hard risk, news,
  portfolio, broker or setup-validation gates.
- Environment memory is persisted to a terminal file and loaded on EA restart.

## Confluence tests

Report both observed conditional slices and true replay variants:

1. Base
2. Base + HTF Order Block
3. Base + Value Area
4. Base + both

Also measure present-vs-absent expectancy for liquidity, market structure,
volatility and news state. Conditional slices are attribution only; they do
not prove causality.

## Architecture ablation

Run separate Strategy Tester passes using identical:

- symbol and date range
- spread model
- commission
- slippage
- fill policy
- initial balance
- risk sizing
- execution settings

Required variants:

- Midas full
- Midas without SMC
- SMC-only
- Regime + non-SMC

The research harness accepts variant-tagged exports and refuses to describe
unreplayed candidate subsets as counterfactual results.

## Walk-forward

```text
training window
    -> learn environment statistics
    -> lock model/evidence
    -> OOS validation window
    -> record metrics
    -> roll forward
```

The validation window is never passed to the learner. The Python research
harness enforces the temporal split with `medis_touch/app/walk_forward.py`.

## Recalibration

Environment memory is evidence for the existing calibration cycle. It does
not directly mutate production parameters. Configuration changes still use:

`Challenger -> evaluation -> Telegram approval -> Champion -> config hash -> EA ACK -> Active`

## Final parity gate

Compare EA and backend telemetry for:

- strategy identity
- regime
- environment key/classification
- confidence
- risk gate
- news gate
- portfolio gate

Any mismatch is a failed parity result; it is not averaged away.

## Important validation boundary

The repository's GitLab CI workflow remains deliberately paused. Static/source
checks can be prepared locally, but only MetaEditor can provide authoritative
MQL5 compilation and the MT5 Strategy Tester can provide actual backtest
results. No compile, profitability, or OOS result should be represented as
proven until those external gates have actually run.
