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

## Runtime selector implementation (branch; validation pending)

The EA now has an explicit `InpAccountProfile` selector:

- `PROP_FIRM` is the default. It copies the existing risk inputs into a separate effective-configuration object, so the existing default values and any intentional prop-firm preset overrides remain the baseline.
- `MICRO_RESEARCH` sets the research risk envelope to 8% risk per trade, 1 maximum open trade, 8.5% portfolio cap, 1 position per symbol/group, 18% daily-loss limit, 35% hard-drawdown halt, 10% de-risk start and 0.25 de-risk floor.
- The profile's resolved limits are routed through order-manager capacity, automated sizing, manual sizing, portfolio limits, daily/drawdown guard initialization and outcome simulation. The original input declarations are not overwritten.
- The active profile and effective risk settings are logged at startup and shown in the chart control panel.
- A terminal Global Variable keyed by account login persists profile identity. A mismatch with a flat account refuses initialization unless `InpConfirmAccountProfileChange=true`. If positions/orders exist, the EA continues managing them under the persisted profile, records the requested switch as pending, and blocks all new automated/manual entries until the account is flat and the EA is reinitialized. Switching does not reset the risk guard's daily baseline, peak equity, hard halt or emergency-stop latch.
- `InpConfirmMicroResearchExecution` defaults to `false`. Manual and automated order submission are blocked in `MICRO_RESEARCH` until it is explicitly enabled; the code also blocks that profile on real-money accounts outside Strategy Tester, even if the acknowledgement is set. Leave it disabled except for controlled testing.
- Profile numeric values are checked for finite values and allowed ranges before initialization. Minimum-lot overrides are forced off so the sizing engine cannot exceed the cash risk budget just to reach a broker's minimum volume.

**Scope boundary:** this is a runtime risk-envelope selector, not a port of the complete StrategyTune micro strategy. The candidate's quality scoring, volatility/spread filters, fallback-entry switches, 10%/20% staged drawdown policy, and consecutive-loss multipliers/pause are not all implemented in this EA profile; source startup logging states this explicitly. The effective micro limits are therefore experimental scaffolding, not strategy parity or profitability evidence.

## Validation gates still required

The static regression tests now cover default compatibility, distinct profile resolution, automated/manual wiring, micro-profile interlocks, persistent profile identity, restart protection invariants, and invalid risk input rejection. GitHub Actions must confirm these tests and the exact MQL5 source compile.

This implementation is **not yet considered complete for live or demo promotion** until the current commit has a successful Windows MetaEditor compile and the actual EA completes matched Strategy Tester runs with spread/commission/slippage, broker-minimum-volume rejection checks, locked out-of-sample evaluation, and restart/partial-fill scenarios. Demo-broker validation must then verify profile lock behavior, broker position reconciliation, and execution recovery. No local MT5 terminal or Exness demo session is available through this repository connection, so those tests cannot be truthfully reported as executed from here.

## Promotion gate for the KSh 1,500 → KSh 10,000 weekly objective

The 566.7% target is a research hypothesis, not a promised or expected return. Report full net P&L, profit factor, expectancy, drawdown, maximum consecutive losses, rejected orders/minimum-volume failures, and results across a locked out-of-sample period. A single winning week is not evidence of repeatability. Never tune or size the strategy solely to force the target.

## Change-control rule

This document is a profile-separation contract. It does not change the live EA defaults or activate the micro profile. The profile switch and any EA integration must be a separate reviewed implementation with tests; the existing `main` branch must not be changed directly by research-only experiments.
