# Top-down MTF decision engine and drawdown-risk controller

## Scope

This candidate adds a direction-agnostic, seven-timeframe context layer in this order:

**D1 → H4 → H1 → M30 → M15 → M5 → M1**

Both BUY and SELL setups are still generated independently by the existing strategy engines. The MTF layer does not create a signal and does not automatically veto every countertrend setup. It adjusts the confidence of each active side by a bounded amount based on independently analysed timeframe contexts. A recent confirmed CHoCH contributes a small, recency-limited reversal adjustment; M1 is deliberately the smallest contributor.

Default weights are D1 30%, H4 24%, H1 18%, M30 10%, M15 8%, M5 6%, M1 4%. The weights sum to 100. The confidence adjustment is capped at ±15 points and defaults to ±8 points. The candidate defaults to **disabled** (InpEnableTopDownMTF=false) so production behavior is not changed before evidence exists. When enabled, inability to load any timeframe fails closed for that automated candidate and is logged; it does not silently fall back to a partial stack.

The timeframe pool was enlarged to support the seven context charts alongside independently configured strategy contexts. If it is full, it now returns NULL instead of quietly returning a context belonging to a different timeframe.

## Separate drawdown-risk control

The account-wide CRiskGuard remains separate from directional analysis. It continues to persist the daily-equity baseline, peak equity and hard-halt state across terminal restarts. The existing peak-to-equity de-risk ramp remains active. An additional daily-loss ladder is implemented behind the explicit input `InpEnableProgressiveDailyLossDeRisk=false` (OFF by default to preserve existing behavior until matched validation). When enabled, it reduces sizing to at most 75% after 25% of the daily loss budget is consumed, at most 50% after 50%, and at most 25% after 75%; at the daily loss cap it returns a zero sizing multiplier. The existing daily-loss/hard-drawdown gates remain authoritative entry blockers. The opt-in setting enables matched risk-only ablation against the current baseline.

The daily and peak-drawdown controls only reduce risk. They never increase position size to recover losses, and no martingale or loss-chasing logic is introduced. Logs record transitions between NORMAL, CAUTION, DEFENSIVE, CRITICAL and HALTED risk states; daily ladder states are reported only when that ladder is enabled.

## Matched validation protocol

Do not compare results produced using different tick data, spread models, EA builds, date windows, or entry/exit settings. Create two initial arms from the same frozen Midas-touch2 source commit and matched .set files:

| Arm | Configuration | Purpose |
|---|---|---|
| A — current strategy | InpEnableTopDownMTF=false; current risk guard behavior | Baseline |
| B — top-down candidate | InpEnableTopDownMTF=true; same MTF weight/adjustment settings on every run | Measure the new decision layer |
| C — drawdown policy ablation | Same as B but use a matched experimental build/preset that disables only the new daily-loss ladder | Attribute the change to the risk-controller ladder |

Arm C requires a declared, versioned test-only switch before running; do not hand-edit EA binaries or silently alter the policy after seeing results. The first implementation has the new daily-loss ladder enabled in code, so A/B alone isolates the MTF layer only when risk behavior is held constant in both compiled builds. For a proper joint assessment, use a baseline build at the parent commit, the candidate build, and a separately reviewed risk-ladder ablation build; record each source SHA and exact inputs.

Run each arm on the same Exness/MT5 demo instrument and broker data where available, using identical dates, symbol, chart/execution timeframe, account balance/currency/leverage, terminal build, fill model, session/news inputs and exits. Execute both BUY and SELL paths; include all instruments intended for production. Use real ticks where available and record whether spread is variable or fixed. Costs must include broker commission, spread, slippage and swaps. Apply any additional stress cost only if it is clearly separated from costs already included in the tester report.

Minimum report per arm:

- Net profit and net return after costs.
- Maximum equity drawdown (absolute and percentage), plus balance drawdown.
- Trade count and frequency by weekday, timeframe, symbol, side (BUY/SELL), trend-aligned/countertrend class, and regime.
- Net expectancy per trade and in R; profit factor; average win/loss; win rate; consecutive losses; time in market; exposure and rejected/blocked candidate counts.
- Long-only and short-only breakdowns to expose asymmetric edges or failure modes.
- Chronological walk-forward evaluation and a locked out-of-sample period not used to select weights or thresholds.
- Sensitivity under widened spread and adverse slippage, followed by MT5 demo forward testing and broker reconciliation.

Interpretation: more trade candidates or a higher number of fills is not a win by itself. The candidate is acceptable only if improvements persist after costs and on out-of-sample data, without unacceptable drawdown or tail-loss behavior. If the MTF layer improves signal quality but lowers valid trade count, that may still be preferable; if it expands frequency but worsens net expectancy or risk-adjusted return, reject or retune it using training data only. Three successful trades per weekday remains a measured aspiration, never a forced quota.

## Evidence status

This branch contains source-level implementation and contract tests. It does not contain genuine MT5 Strategy Tester results for the new MTF candidate, a broker-demo forward run, or live profitability evidence. Those must be generated from the native EA with the actual MT5 terminal and broker dataset. CI compilation and Python contract tests are necessary software checks, not proof that the strategy is profitable or production-ready.
