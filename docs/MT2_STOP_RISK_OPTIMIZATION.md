# Midas-touch2 stop-loss and risk optimization protocol

## Decision principle

Optimize cost-adjusted expectancy and drawdown per unit of opportunity—not the smallest possible trade count. A stop defines intended exposure; it cannot guarantee small realized losses because gaps, slippage, liquidity and rejected modifications can change the fill. Trailing protection, partial exits, entry edge and portfolio sizing must be measured separately.

The EA already enables InpEnableDynamicStop=true. Defaults activate dynamic protection at +0.75R, begin break-even protection at +1R, use a 1.50 ATR fallback, prefer confirmed structural anchors, and limit successful modification frequency to one per five seconds. Default account settings remain 0.50% risk per trade, 3% daily loss cap, 10% hard drawdown cap, de-risking from 5% with a 25% floor, 3% portfolio open-risk cap, three open trades, and three positions per symbol/correlation group. These are the baseline—not a claim of optimality.

Do not replace defaults with tighter or looser settings merely because they sound safer or more profitable. Preserve the original small-account and prop-firm presets. Run separate experiments with account_profile set to small_account and prop_firm; each needs its real preset and account context. Before any prop-firm experiment, verify every candidate against the firm's daily/equity-loss, trailing-drawdown, lot, exposure, news and holding rules. The comparator does not encode each firm's full rule book.

## Position-management correction

Partial profit taking is an exit rule, not a side effect of a successful stop modification. The position manager now delegates partial-close eligibility to PositionManagementPolicy.mqh. A live position in TS_FILLED or TS_PROTECTED can reach InpPartialAtR; state advances only after the broker confirms the partial close. Thus a trailing-off ablation no longer silently disables the partial-close path. The broker adapter remains responsible for actual close result and state transitions.

## Five-arm matched experiment

Use the same symbol, timeframe, immutable tick snapshot, account balance/currency/leverage, EA source/build, terminal build, entry rules, strategy inputs, sessions, tester fill model and execution assumptions across every arm. Preserve each actual .set file exported from the run.

| Arm | Purpose | Permitted change from A |
|---|---|---|
| A_current_baseline | Current reference | None; dynamic trailing enabled |
| B_trailing_off | Causal ablation | InpEnableDynamicStop=false only |
| C_trailing_candidate | Test one trailing candidate | Trailing/position-management parameters only; trailing remains enabled |
| D_tight_risk | Proposed restrictive settings | Risk settings only |
| E_calibrated_risk | Profile-specific risk candidate | Risk settings only; must not duplicate D |

D is the previously proposed restrictive candidate, not a recommendation: risk per trade 0.35%; maximum open trades 2; daily loss cap 2%; hard drawdown cap 8%; de-risk start 3%; de-risk floor 0.15; portfolio open-risk cap 1.5%; maximum positions per symbol 2; maximum positions per group 2. E must be predeclared based on profile-specific constraints and evidence, and preserve A's exact trailing/partial settings. If D conflicts with binding rules, do not run it; adapt the experiment contract and validator deliberately rather than bypassing a guard.

Every arm needs identical preset cost inputs and must declare costs actually applied inside Strategy Tester: variable spread and widening stress (multiplier at least 1.01), non-zero commission, slippage and swaps. For real-tick spread, record spread_points=null rather than inventing a fixed quote. Do not subtract spread/slippage twice if their effects already appear in executed fills. Net position cashflow sums deal profit + commission + swap + fee.

## Required artifacts and input data

For each arm retain the actual tester .set, report HTML, completed/partial deal CSV, open-position ID CSV and shared immutable tick archive. Hash the archive using SHA-256. Each variant repeats observed context so mismatched profile/build/cost settings are rejected. Deal CSV columns are position_id,time,entry,volume,profit,commission,swap,fee,risk_cash. Each deal row uses positive volume and entry values in, out or out_by (or MT5 numeric 0, 1, 3). Split inout reversals into close/open rows. Entry rows must contain initial monetary risk. Incomplete/open positions are excluded, not assigned synthetic outcomes.

The context requires profile, symbol/timeframe, declared period, locked OOS window, tick-data digest, EA source SHA/build, terminal build, vendor, stressed spread model, spread widening multiplier, commission/slippage, swap inclusion, fill policy, initial balance, currency and leverage. Declarations must match actual artifacts; hashes establish file identity, not that a tester was configured truthfully.

## Run and interpret

From repository root, after obtaining genuine MT5 exports:

    python tools/risk_trailing_experiment.py --manifest path/to/manifest.json --output path/to/comparison.json
    python -m pytest -q tools/tests/test_risk_trailing_experiment.py tools/tests/test_position_management_contract.py

The JSON reports net expectancy, profit factor, average wins/losses, consecutive losses, closed-position drawdown, deterministic trade-order Monte Carlo drawdown percentiles, full-period and frozen OOS metrics, and deltas against A. It never auto-promotes settings.

Monte Carlo permutes completed returns without replacement. This tests sensitivity to trade order; it is not a forecast or proof of tail risk. Closed-position drawdown omits intratrade equity excursions. Keep the native MT5 balance/equity curve and tester drawdown report with the JSON. Require sufficient sample size and regime/symbol coverage, walk-forward tests, an untouched out-of-sample interval, then demo-broker forward validation.

The target of three qualified successful trades per weekday is measured, never forced. Zero qualified trades in a regime is valid evidence; do not lower the entry threshold merely to hit a quota. Never tune against the locked OOS period after reviewing it.

## Validation boundary

Python tests and MQL5 structural checks can run in CI. EA/tests/PositionManagementPolicy.mq5 and EA/tests/DynamicStopEngine.mq5 are terminal-side test scripts, not proof that MetaEditor compiled them. Release still requires MetaEditor compilation in the target MT5 include environment, native Strategy Tester comparisons for all arms, demo-broker validation, and production bridge/broker reconciliation. A green GitHub Actions run must not be presented as evidence that those external checks happened.
