# MidasTouch2 — MT5 opposing-position demo validation gate

Status: **not yet run against an Exness demo terminal**. CI tests below exercise deterministic policy only; they do not create broker positions.

## 1. Preconditions

- Use a dedicated **Exness demo** account, not the live account.
- Confirm the actual terminal reports `ACCOUNT_MARGIN_MODE_RETAIL_HEDGING`. Do not infer the mode from the account label.
- Deploy the exact compiled EA build from this repository's `main` and record the EA source SHA, EX5 hash, MT5 terminal build, broker server, symbol, account currency, balance, leverage, and symbol contract settings.
- Confirm the broker execution ledger is healthy if `InpRequireExecutionLedger=true`; otherwise the EA must remain blocked.
- Leave `InpEnableDynamicStop=true`; do not disable trailing protection.
- Start with a clean chart-symbol state: no manual positions, other-EA positions, or pending orders on that symbol.

## 2. Risk-profile constraint

The shipped small-account profile deliberately sets `InpSmallMaxOpenTrades=1` and `InpSmallMaxPositionsPerSymbol=1`, with a 0.5% portfolio open-risk cap. With those limits, concurrent opposing positions are correctly prevented by portfolio caps even on a hedging account. **Do not relax those limits on the live account to enable the feature.**

For an isolated demo capability test only, explicitly configure a valid profile that permits two positions on the same symbol. The open-risk cap must cover both stop-risk amounts while remaining at or below the daily-loss cap. Keep each stop-defined trade risk small, do not enable minimum-lot overrides, and abort if the broker minimum lot exceeds the configured risk. Profile validation, aggregate portfolio risk and max-position controls are expected to block any configuration that does not satisfy these constraints.

## 3. Required demo scenarios

Record the Experts/Journal logs, execution-audit CSV, broker deal history, position tickets, SL/TP and order/position identifiers for every step.

1. **Default-off check:** set `InpAllowConcurrentOpposingPositions=false`. When a valid opposite-side entry is attempted while a same-symbol position exists, it must be blocked with `AUTOMATED_BLOCKED_OPPOSING_EXPOSURE` or `MANUAL_BLOCKED_OPPOSING_EXPOSURE`; there must be no second opposite ticket.
2. **Netting fail-closed check:** on a separate netting demo account, request the input on but keep existing same-symbol exposure. The EA must refuse the additional entry and must not claim both sides are independently open.
3. **Hedging buy-then-sell check:** on the verified hedging demo, enable the input and configured two-position risk envelope. Open one small BUY, then a separately authorized valid SELL. Verify two distinct position identifiers/tickets, the expected direction of each, separate SL/TP, separate ledger attribution, and aggregate stop risk within the configured portfolio cap.
4. **Hedging sell-then-buy check:** reverse the sequence. Verify the same properties in the opposite order.
5. **Trailing-stop check:** allow a position to pass the configured stop-activation condition, then confirm the broker SL modification is accepted per ticket. Verify a tighter stop is never widened, and one position's update is not applied to the other ticket.
6. **Partial close and restart:** on demo only, execute a supported partial close and restart the EA/terminal. Confirm each remaining position is reconciled once, its SL is still present, position ownership is not cross-bound, and entry/exit deals are not duplicated in the ledger.
7. **Risk-cap rejection:** construct a candidate whose addition would breach the open-risk or position limit. It must be rejected; the daily trade target must not bypass the rejection.
8. **Disable / emergency stop:** turn the input off while opposite positions already exist. Verify no new opposite entry is admitted; do not assume existing positions are automatically closed. Trigger the emergency stop and verify new entry admission stays blocked after restart.

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
