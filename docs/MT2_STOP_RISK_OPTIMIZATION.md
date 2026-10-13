# Midas-touch2 stop-loss and risk optimization protocol

## Decision principle

Optimize cost-adjusted expectancy and drawdown per unit of opportunity—not the smallest possible trade count. A stop defines intended exposure; it cannot guarantee small realized losses because gaps, slippage, liquidity and rejected modifications can change the fill. Trailing protection, partial exits, entry edge and portfolio sizing must be measured separately.

The EA already enables InpEnableDynamicStop=true. Defaults activate dynamic protection at +0.75R, begin break-even protection at +1R, use a 1.50 ATR fallback, prefer confirmed structural anchors, and limit successful modification frequency to one per five seconds. Default account settings remain 0.50% risk per trade, 3% daily loss cap, 10% hard drawdown cap, de-risking from 5% with a 25% floor, 3% portfolio open-risk cap, three open trades, and three positions per symbol/correlation group. These are the baseline—not a claim of optimality.

Do not replace defaults with tighter or looser settings merely because they sound safer or more profitable. The EA now has an explicit `InpAccountRiskProfile` selector:

- `ACCOUNT_RISK_PROFILE_LEGACY_INPUTS` (default): reads the original risk inputs, preserving behavior for existing .set files and the current baseline.
- `ACCOUNT_RISK_PROFILE_SMALL_ACCOUNT`: reads only the independently configurable `InpSmall*` risk settings.
- `ACCOUNT_RISK_PROFILE_PROP_FIRM`: reads only the independently configurable `InpProp*` risk settings.

All nine limits—risk per trade, max open trades, daily loss cap, hard drawdown cap, de-risk start, de-risk floor, portfolio open-risk cap, max positions per symbol and per correlation group—are resolved together before strategy startup. Both automated and operator/manual order entry use that single resolved profile. Invalid profiles fail closed before order routing. The account-wide daily baseline, peak-equity halt and persistent hard-stop state remain shared across EA restarts; changing profile does not reset accumulated drawdown or clear a halt.

The small-account and prop-firm inputs intentionally mirror the legacy values by default. This is a backward-compatible starting point, **not a claim that these values are optimal for small accounts or compliant with a particular prop firm**. Set small-account values only after the matched comparison. Set prop-firm values to the exact firm's binding daily-loss, maximum-drawdown/trailing-drawdown and position/exposure rules before enabling that profile. Do not infer a firm's contract from the generic defaults.

Run separate experiments with `account_profile` set to `small_account` and `prop_firm`; each requires its actual preset and account context. Every arm must retain its selected `InpAccountRiskProfile` enum value (`1` for small-account, `2` for prop-firm), and only the selected profile's risk input group may vary in D/E. The validator rejects differences to inactive profiles. Before any prop-firm experiment, verify every candidate against the firm's daily/equity-loss, trailing-drawdown, lot, exposure, news and holding rules. The comparator cannot encode the full rule book automatically.

## Position-management correction

Partial profit taking is an exit rule, not a side effect of a successful stop modification. The position manager now delegates partial-close eligibility to PositionManagementPolicy.mqh. A live position in TS_FILLED or TS_PROTECTED can reach InpPartialAtR; state advances only after the broker confirms the partial close. Thus a trailing-off ablation no longer silently disables the partial-close path. The broker adapter remains responsible for actual close result and state transitions.

## Five-arm matched experiment

Use the same symbol, timeframe, immutable tick snapshot, account balance/currency/leverage, EA source/build, terminal build, entry rules, strategy inputs, sessions, tester fill model and execution assumptions across every arm. Preserve each actual .set file exported from the run.

| Arm | Purpose | Permitted change from A |
|---|---|---|
| A_current_baseline | Current reference | None; dynamic trailing enabled |
| B_trailing_off | Causal ablation | InpEnableDynamicStop=false only |
| C_trailing_candidate | Test one trailing candidate | `InpDynamicStop*` parameters only; trailing remains enabled. Partial target/fraction, break-even and simulator exit inputs stay identical to A |
| D_tight_risk | Proposed restrictive settings | Risk settings only |
| E_calibrated_risk | Profile-specific risk candidate | Risk settings only; must not duplicate D |

C may tune only the live dynamic-stop controls; do not change `InpPartialAtR`, `InpPartialFraction`, `InpBreakEvenAtR`, or legacy simulator exit inputs in that arm because they would confound trailing attribution. D is the previously proposed restrictive candidate, not a recommendation: risk per trade 0.35%; maximum open trades 2; daily loss cap 2%; hard drawdown cap 8%; de-risk start 3%; de-risk floor 0.15; portfolio open-risk cap 1.5%; maximum positions per symbol 2; maximum positions per group 2. For small-account E, the current challenger holds per-trade risk, daily loss cap, hard drawdown cap, de-risking, and portfolio open-risk cap equal to A while testing greater capacity (max open trades 5, positions per symbol/group 4). This tests whether the current concurrency limits suppress valid opportunities without increasing the configured aggregate stop-risk budget; existing portfolio admission must still reject a batch that breaches its risk cap. E is research-only until measured. The validator does not allow a prop-firm E to loosen the verified firm's baseline risk or position limits. Every arm preserves A's exact trailing/partial settings outside the one permitted B/C trailing change. If D conflicts with binding rules, do not run it; adapt the experiment contract and validator deliberately rather than bypassing a guard.

Every arm needs identical preset cost inputs and a truthful base-cost declaration: the Strategy Tester/deal history must already include the actual broker commission, historic spread from real ticks, and swaps. The analysis harness then adds an explicit adverse stress on top: spread widening with multiplier >1.01 and a positive slippage-point charge on each executed deal. This split is intentional because the current MetaEditor CI does not configure or verify a per-deal slippage model in the Strategy Tester. For real-tick spread, record spread_points=null rather than inventing a fixed spread. Supply baseline_spread_points from the tick snapshot plus cash_per_point_per_lot from the exact broker/account instrument contract; the harness applies only the incremental widening above the spread already paid. It applies slippage_points × cash_per_point_per_lot × executed turnover volume. Net P&L is deal profit + signed commission + signed swap + signed broker fee minus incremental spread-widening and additional slippage stress.

## Required artifacts and input data

For each arm retain the actual tester .set, report HTML, completed/partial deal CSV, open-position ID CSV and shared immutable tick archive. Hash the archive using SHA-256. Each variant repeats observed context so mismatched profile/build/cost settings are rejected. Deal CSV columns are position_id,time,entry,volume,profit,commission,swap,fee,risk_cash. Each deal row uses positive volume and entry values in, out or out_by (or MT5 numeric 0, 1, 3). Split inout reversals into close/open rows. Entry rows must contain initial monetary risk. Incomplete/open positions are excluded, not assigned synthetic outcomes.

The context requires profile, symbol/timeframe, declared period, locked OOS window, tick-data digest, EA source SHA/build, terminal build, vendor, spread-stress model, spread widening multiplier, base spread in points, cash value per point per lot, commission/slippage, base-cost and analysis-stress flags, swap inclusion, fill policy, initial balance, currency and leverage. Use the broker's actual tick size/value/contract-size calculations for cash_per_point_per_lot; do not estimate it from a generic symbol label. Declarations must match actual artifacts; hashes establish file identity, not that a tester was configured truthfully.

## Run and interpret

From repository root, after obtaining genuine MT5 exports:

    python tools/risk_trailing_experiment.py --manifest path/to/manifest.json --output path/to/comparison.json
    python -m pytest -q tools/tests/test_risk_trailing_experiment.py tools/tests/test_position_management_contract.py

The JSON reports net expectancy, profit factor, average wins/losses, consecutive losses, closed-position drawdown, deterministic trade-order Monte Carlo drawdown percentiles, full-period and frozen OOS metrics, chronological fixed-parameter walk-forward slices, and deltas against A. Each walk-forward test window is strictly before the locked-OOS start and is scored only with fully closed positions wholly inside that window; positions crossing a window boundary are censored, not fabricated as wins or losses. The walk-forward slices are an evaluation of frozen configurations, not automatic parameter fitting. The harness never auto-promotes settings.

Monte Carlo permutes completed returns without replacement. This tests sensitivity to trade order; it is not a forecast or proof of tail risk. Closed-position drawdown omits intratrade equity excursions. Keep the native MT5 balance/equity curve and tester drawdown report with the JSON. Require adequate samples, regime/symbol coverage and consistent forward-window results, then evaluate the frozen candidate on the untouched locked-OOS window and on a future holdout. Finally run demo-broker forward validation.

The target of three qualified successful trades per weekday is measured, never forced. Zero qualified trades in a regime is valid evidence; do not lower the entry threshold merely to hit a quota. Never tune against the locked OOS period after reviewing it.

## Validation boundary

Python tests and MQL5 structural checks run in CI. The Windows MetaEditor workflow compiles the main EA, `EA/tests/PositionManagementPolicy.mq5`, and `EA/tests/AccountRiskProfilePolicy.mq5` on the candidate. The two test scripts' `OnInit` assertions are compiled but are not automatically executed by the compile job. `EA/tests/DynamicStopEngine.mq5` is still not compiled/executed by that workflow. A green Python/MetaEditor pipeline demonstrates software and source-contract checks, not trading profitability. Release still requires native Strategy Tester comparisons using genuine exports for every arm, tester-native equity-drawdown evidence, demo-broker forward validation, and production bridge/broker reconciliation. These external runtime checks are not complete just because a comparison tool is implemented.
