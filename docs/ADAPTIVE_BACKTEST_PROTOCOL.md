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

Memory is updated **after** an outcome resolves. A future decision may use only outcomes whose timestamps precede that decision. This is online learning, not look-ahead optimization.

## Evidence controls

- Minimum resolved sample per environment/strategy cell: 30 by default.
- A positive adjustment requires positive expectancy, profit factor > 1 and a 95% Wilson lower bound >= 50% win rate.
- A negative adjustment requires twice the minimum sample plus negative expectancy, profit factor < 1 and a 95% Wilson upper bound < 50%.
- Historical adjustments are bounded and never bypass hard risk, news, portfolio, broker, or setup-validation gates.
- Environment memory persists to the MT5 terminal and is isolated from Strategy Tester memory.

## Confluence tests

Report both observed conditional slices and true replay variants:

1. Base
2. Base + HTF Order Block
3. Base + Value Area
4. Base + both

Also measure present-vs-absent expectancy for liquidity, market structure, volatility and news state. Conditional slices are attribution diagnostics only; they do not establish causal counterfactuals.

## Architecture ablation

Run separate Strategy Tester passes with identical:

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

The research harness accepts variant-tagged exports as genuine variant results. Untagged subsets are never represented as counterfactual backtests.

## SMC-inclusive self-test

SMC is part of the same self-test loop as Momentum, Mean Reversion and Key-Level. The self-test must measure SMC itself and its interaction with peer strategies before forward testing.

At minimum, the replay matrix must cover:

- liquidity-sweep requirement
- BOS confirmation requirement
- FVG requirement and maximum FVG distance in ATR
- impulse and internal-structure requirements
- SMC selection/confidence threshold
- HTF Order Block relationship
- Value Area relationship
- invalidation and stop geometry
- target construction
- SMC candidate/trade frequency
- SMC expectancy by market regime
- contribution versus the Midas baseline
- contribution versus non-SMC strategies

The existing implementation provides `medis_touch/app/smc_self_test.py` for the OOS stability and promotion gate. It deliberately does **not** optimize on the validation window.

## SMC parameter stability gate

Candidate configurations are evaluated on locked OOS replay results. A candidate must satisfy the OOS quality gates and sit on a performance plateau rather than being a single sharp optimum.

Default requirements:

- positive OOS expectancy
- profit factor >= 1
- complete finite OOS metrics
- OOS degradation <= 35%
- at least one nearby configuration within 10% of the selected candidate's OOS expectancy

The implementation rejects a configuration when the apparent optimum has no stable neighbor. This is a robustness test, not a claim that the chosen parameters are globally optimal.

The winning SMC configuration is then frozen by deterministic SHA-256 configuration identity. Forward-test parameters must match that hash exactly; drift fails closed. The freeze record also stores the Strategy Tester variant and data version used to establish it.

## Walk-forward

```text
training window
    -> learn environment/strategy evidence
    -> evaluate candidate SMC configurations
    -> lock candidate
    -> locked OOS window
    -> record metrics and degradation
    -> stability/promotion gate
    -> roll forward
```

The validation window is never passed to the learner. SMC parameter changes are not made from the same observations used to evaluate them.

## Recalibration

Environment memory is evidence for the existing calibration cycle. It does not directly mutate production parameters. Configuration changes still follow:

`Challenger -> evaluation -> Telegram approval -> Champion -> config hash -> EA ACK -> Active`

## Final parity gate

Compare EA and backend telemetry for:

- strategy identity
- regime
- environment key/classification
- SMC eligibility and diagnostics
- SMC parameter/configuration hash
- confidence
- risk gate
- news gate
- portfolio gate

Any mismatch is a failed parity result; it is not averaged away.

## Important validation boundary

The repository's GitLab CI workflow remains deliberately paused. Static/source checks can be prepared, but only MetaEditor provides authoritative MQL5 compilation and the MT5 Strategy Tester provides actual MQL5 historical backtest results.

No compile, profitability, OOS, parameter-stability, or forward-test result is considered proven until the corresponding external test has actually run.
