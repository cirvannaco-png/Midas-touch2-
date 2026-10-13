# Midas Touch 2 account profiles

## Safety contract

Midas Touch 2 must preserve the existing prop-firm/standard-account configuration while the small-account work remains a separate, opt-in research profile. Do not replace the EA's current default inputs with the aggressive micro-account values. Do not promote research settings into live trading by default.

The production EA source of truth is `EA/MedisTouch_v2.8.mq5`. The values below were checked against the current `main` source. A profile implementation must preserve these defaults exactly unless a separately reviewed change explicitly authorizes otherwise.

## Profile A — Prop-firm / existing default (preserve)

| EA input | Existing `main` default |
|---|---:|
| `InpRiskPercentPerTrade` | 0.5% |
| `InpMaxOpenTrades` | 3 |
| `InpMaxPortfolioRiskPercent` | 3.0% |
| `InpMaxPositionsPerSymbol` | 3 |
| `InpMaxPositionsPerGroup` | 3 |
| `InpMaxDailyLossPercent` | 3.0% |
| `InpMaxDrawdownPercent` | 10.0% |
| `InpDeriskStartPercent` | 5.0% |
| `InpDeriskFloor` | 0.25 |
| `InpAllowMinLotOverride` | false |

This is the compatibility baseline. Keep all other current EA inputs unchanged too. Do not silently reduce open-trade/portfolio capacity or alter trailing, execution, entry, recovery, or bridge behavior as part of the micro-account work.

## Profile B — KSh micro-account (research only)

The aggressive small-account work remains a separate StrategyTune research artifact:

- Script: `MT2 KSh Micro-Account Aggressive Research`
- Script ID: `jnmbgayw8f14jrm3uvsq4cbz`
- Last checked version: 3; compile succeeded.
- Intended research balance: KSh 1,500 converted to the run's account currency using a documented rate for each run.
- Research inputs include 8% base risk, 8% per-trade cap, one concurrent position, 8.5% portfolio open-risk cap, 18% daily-loss threshold, drawdown risk reductions at 10% and 20%, a 35% maximum-drawdown entry circuit breaker, quality threshold 68, volume confirmation (RVOL 1.2), ATR regime bounds 0.65–1.8, and spread/ATR maximum 0.20.
- Lower-quality fallback entries are disabled; the candidate grades price location and combines overlapping displacement/structure evidence to reduce double counting.

**Research status:** compiled, not proven profitable. A new small-account backtest has not completed because the StrategyTune daily cloud-compute quota was exhausted. The artifact has not been ported into or validated in the production MT5 EA. StrategyTune does not model commission or slippage natively.

These values are deliberately documented as research parameters, not as approved production settings. Do not copy the 8% risk or other aggressive thresholds into the live EA or the prop-firm profile.

## Required implementation design

Any future EA profile switch must be explicit and fail-safe:

1. Default profile remains `PROP_FIRM` / existing defaults.
2. `MICRO_RESEARCH` is opt-in and must be visibly identified in the EA log and chart/control panel.
3. Keep independent effective parameters for risk per trade, concurrency, portfolio caps, daily loss, drawdown, and de-risk behavior. Never mutate the saved input values or silently reuse one profile's settings for the other.
4. Validate risk against broker minimum volume, symbol contract/tick values, stop distance, margin, account currency, and the actual order result. Reject trades that cannot fit the risk budget; never force a minimum lot that exceeds it.
5. Apply profile changes only to new entries. Manage/reconcile existing positions with the settings and identity under which they were opened.
6. Add tests proving that the prop-firm defaults are unchanged, profiles do not leak into one another, restart recovery preserves profile identity, and invalid/missing profile values fail closed.
7. Do not call the micro profile production-ready until MetaEditor compilation, Strategy Tester tests with costs, locked out-of-sample testing, and demo-broker validation pass.

## Promotion gate for the KSh 1,500 → KSh 10,000 weekly objective

The 566.7% target is a research hypothesis, not a promised or expected return. Report full net P&L, profit factor, expectancy, drawdown, maximum consecutive losses, rejected orders/minimum-volume failures, and results across a locked out-of-sample period. A single winning week is not evidence of repeatability. Never tune or size the strategy solely to force the target.

## Change-control rule

This document is a profile-separation contract. It does not change the live EA defaults or activate the micro profile. The profile switch and any EA integration must be a separate reviewed implementation with tests; the existing `main` branch must not be changed directly by research-only experiments.
