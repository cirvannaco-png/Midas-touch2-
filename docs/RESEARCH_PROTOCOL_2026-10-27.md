# Midas-touch2 research protocol — 2026-10-27

Status: research-only; no production settings changed; no performance claim.

## Risk-profile change in this branch

The small-account profile requests a 50% daily-loss cap. The profile validator requires the hard drawdown ceiling to exceed the daily cap, so this research branch pairs it with a 55% hard drawdown ceiling. On a KSh 1,500 balance, a 50% daily-loss allowance is KSh 750 before fees, slippage or gaps. These are catastrophic-loss limits, not safe operating targets. This branch must not be merged or deployed until the owner reviews this consequence and historical and demo gates pass. Existing production remains unchanged.

The 15–20% per-trade risk profile is the small-account profile per the owner's clarification. The 20% hard per-trade ceiling, 15% minimum admitted risk, 20% portfolio open-risk cap, dynamic stop requirement, minimum-volume rejection, and required execution ledger remain in force. If minimum broker volume risks more than the allowed trade budget, reject the trade. Do not loosen stop distances or force a trade to meet a daily trade count.

## Research design

### 1. Freeze instrument and execution assumptions

Before running any variant, freeze the exact EA commit, compiled EX5 hash, MT5 terminal build and .set file; Exness demo symbol contract, tick size/value, volume min/step/max, stop/freeze levels, account currency, leverage and margin mode; real-tick history and date range with file hash or reproducible broker data identifier; actual commission and swap/financing settings; bid/ask spread; documented slippage model and stress scenarios; initial equity, profile, portfolio limits, magic number and fill policy.

Do not describe a run as fully cost-inclusive if any cost is missing. Do not mix StrategyTune/LONA simulator results with MT5 EA results as if they were equivalent.

### 2. Development-only experiment matrix

Use only the development segment for parameter selection. Change one family at a time and keep all other inputs fixed:

1. Entry quality: predeclared score/displacement/FVG-proximity thresholds and stale-setup/chase rejection.
2. Market regime: volatility, trend/chop, session and news regime gates. Report results by regime as well as in aggregate.
3. Exits: TP1/TP2 fractions, break-even transition and trailing activation/distance. Do not claim a trailing benefit unless a real trade activates the trail.
4. Risk controls: minimum-volume rejection, sizing against stop distance and costs, per-trade risk, open portfolio risk, daily-loss and hard-drawdown gates, concurrent position count, and behavior after partial exits.

Keep a predeclared baseline and a small, justified candidate set. Do not run broad untracked parameter sweeps. Record every tested variant, rationale, configuration hash and result, including failed variants.

### 3. Chronological walk-forward

Partition available historical development data into at least three chronological folds. In each fold, select only on the earlier development slice and evaluate on the immediately subsequent slice. Do not random-shuffle market observations. Do not revisit earlier folds to choose a winner after seeing later results.

After development choices are frozen, evaluate the selected candidate and unchanged baseline on a separately designated locked final window. Register its dates and hashes before opening results. No parameter changes are permitted after inspecting the locked window; any change invalidates that window and requires a new untouched period.

Keep open or boundary-crossing positions censored/unresolved, not wins or losses. Aggregate partial closes by position identifier. Do not count close rows as separate trades.

### 4. Metrics and selection gates

For baseline and each declared candidate, report net P&L after all costs, expectancy per completed position and realized R; profit factor; position-level win rate with confidence interval; equity drawdown; maximum loss streak and loss-size asymmetry; completed position count, unresolved positions, trade frequency and no-trade periods; commissions, swap, spread and slippage contribution; and minimum-volume/risk-limit rejection counts. Report direction, session and regime splits only where sample size supports interpretation.

Reject candidates that only improve development results, degrade any chronological holdout, depend on an unexercised trail, or fail cost/slippage sensitivity. Treat 87% accuracy and 600% return as aspirations, not tuning objectives to overfit. Report confidence intervals and never imply that a small sample establishes 87% performance.

### 5. Exness demo forward gate

After historical comparison, run the unchanged candidate on a dedicated Exness demo account. Capture exact EA commit/build hash, terminal build, .set file, account margin mode and symbol specification; MT5 Experts/Journal logs showing EXECUTION_LEDGER_READY after startup reconciliation; broker order/deal exports and EA audit CSV with entry/exit deal IDs, timestamps, volumes, prices, commission, swap, fees and protective-stop changes; accepted/rejected stop modification results including broker retcodes, stop/freeze distance and tick-size validation; reconciliation showing no unexplained differences between broker positions/deals, durable ledger and EA state; and partial-close, restart/recovery and emergency-stop checks.

If the ledger reports EXECUTION_LEDGER_CONFIGURATION_MISSING or EXECUTION_LEDGER_NOT_READY, block new entries. Do not add secrets to source or logs. If the broker rejects a protective-stop modification or any fill/cost cannot be reconciled, stop the test and reject promotion.

## Promotion rule

No live deployment, Render change, production environment-variable change, merge, or live order is authorized by this research plan. Promotion requires review of cost-inclusive matched reports, all chronological folds, the locked final test, and successful Exness demo-forward reconciliation. The 50% daily-loss and 55% drawdown values require explicit risk review before any production consideration.