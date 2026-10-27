# MidasTouch2 — MT5 opposing-position demo validation gate

Status: **not yet run against an Exness demo terminal**. CI tests below exercise deterministic policy only; they do not create broker positions.

## 1. Preconditions

- Use a dedicated **Exness demo** account, not the live account.
- Confirm the actual terminal reports `ACCOUNT_MARGIN_MODE_RETAIL_HEDGING`. Do not infer the mode from the account label.
- Deploy the exact compiled EA build from this repository's `main` and record the EA source SHA, EX5 hash, MT5 terminal build, broker server, symbol, account currency, balance, leverage, and symbol contract settings.
- Confirm the broker execution ledger is healthy if `InpRequireExecutionLedger=true`; otherwise the EA must remain blocked.
- Leave `InpEnableDynamicStop=true`; do not disable trailing protection.
- Start with a clean chart-symbol state: no manual positions, other-EA positions, or pending orders on that symbol. The EA now fail-closes on foreign same-symbol exposure because that risk cannot be isolated in this instance's ledger.

## 2. Risk-profile constraint

**Small account — default:** the KSh 1,500 account uses the conservative small-account profile: 0.5% planned stop risk per trade (KSh 7.50 at KSh 1,500 equity), one open position, 1.5% daily-loss cap, 5% hard drawdown cap, and 0.5% portfolio open-risk cap. This profile deliberately cannot open simultaneous opposing positions; its maximum is one trade.

**Large account — separate high-risk profile:** `ACCOUNT_RISK_PROFILE_LARGE_ACCOUNT` (enum 3) retains `InpLargeMinimumRiskPercentPerTrade=15.0`, `InpLargeRiskPercentPerTrade=20.0`, three configured positions, 25% daily-loss cap, 35% hard drawdown cap, and 20% portfolio open-risk cap. This profile is not for the KSh 1,500 account and must not be selected on live capital while the validation gates remain open.

For opposing-position capability testing, use a dedicated Exness demo hedging account and isolate the test from all live funds. The two-direction test must use an explicitly reviewed demo preset with coherent risk caps; do not simply select the large-account 15–20% profile to bypass the small-account one-position ceiling. If no dedicated low-risk demo test preset is available, mark the hedging scenario **not exercised** until one exists. Do not enable minimum-lot overrides, and abort whenever broker volume would breach the approved stop-risk budget.

## 3. Required demo scenarios

Record the Experts/Journal logs, execution-audit CSV, broker deal history, position tickets, SL/TP and order/position identifiers for every step.

1. **Default-on hedging check:** confirm `InpAllowConcurrentOpposingPositions=true` is the shipped default. On a verified retail-hedging demo, a separately authorized valid opposite-side entry may open a second independent ticket only if every strategy, stop, ledger and portfolio-risk gate passes. If any gate fails, it must be blocked and logged; default-on must not force an entry.
2. **Netting fail-closed check:** on a separate netting demo account, request the input on but keep existing same-symbol exposure. The EA must refuse the additional entry and must not claim both sides are independently open.
3. **Hedging buy-then-sell check:** on the verified hedging demo, enable the input and configured two-position risk envelope. Open one small BUY, then a separately authorized valid SELL. Verify two distinct position identifiers/tickets, the expected direction of each, separate SL/TP, separate ledger attribution, and aggregate stop risk within the configured portfolio cap.
4. **Hedging sell-then-buy check:** reverse the sequence. Verify the same properties in the opposite order.
5. **Trailing-stop check:** allow a position to pass the configured stop-activation condition, then confirm the broker SL modification is accepted per ticket. Verify a tighter stop is never widened, and one position's update is not applied to the other ticket.
6. **Partial close and restart:** on demo only, execute a supported partial close and restart the EA/terminal. Confirm each remaining position is reconciled once, its SL is still present, position ownership is not cross-bound, and entry/exit deals are not duplicated in the ledger.
7. **Risk-cap rejection:** construct a candidate whose addition would breach the open-risk or position limit. It must be rejected; the daily trade target must not bypass the rejection.
8. **Opt-out / emergency stop:** set the input false and verify no new opposite entry is admitted; do not assume existing positions are automatically closed. Trigger the emergency stop and verify new entry admission stays blocked after restart.

## 4. Acceptance criteria

Pass only with captured broker evidence for both entry orders, two independently selectable position tickets, per-ticket SL updates, close/restart recovery, no duplicate ledger deals, no unbounded aggregate risk, and no unexpected netting reversal. A policy-test pass or MetaEditor compile alone is not a demo pass. If a scenario cannot be triggered without weakening strategy filters, record it as **not exercised**, not as passed.

## 5. Evidence bundle

Attach:
- exact EA source commit and EX5 hash;
- account-margin-mode line from startup audit;
- MT5 Experts and Journal logs;
- execution audit CSV and ledger reconciliation output;
- broker deal/history export with commissions, swaps and fees;
- position snapshots before/after restart;
- result per scenario with any blocked reason.

No scenario should be run on live capital as part of this gate.
