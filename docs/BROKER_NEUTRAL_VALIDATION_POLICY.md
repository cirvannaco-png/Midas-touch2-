# Broker-neutral MT5 validation policy

## Design boundary

Midas-touch2 is an MT5 Expert Advisor intended to operate through the broker account selected in the connected MetaTrader 5 terminal. It must not require Exness-specific credentials, server names, account IDs, time offsets, symbol names, or execution assumptions.

The supported execution boundary is the MT5 terminal and its live account/symbol contract. A broker may be selected freely, but each selected account and symbol must satisfy runtime checks and pass the same evidence gates before any live use. A broker name is not a capability guarantee.

## Runtime discovery and validation

At initialization and before sizing/submission, capture and validate the actual terminal/account/symbol properties needed by the operation:

- Account currency, balance/equity, leverage, margin mode (netting or hedging), trade permissions, account/server identity.
- Symbol trade mode, point/digits, contract size, tick size, tick value (including profit/loss values where available), volume minimum/maximum/step/limit.
- Stop level, freeze level, filling and execution modes, trading sessions, quote freshness, bid/ask spread, and margin required for the proposed volume.
- Broker-side acceptance/rejection responses and authoritative order, deal, and position identifiers.

Unavailable, non-finite, contradictory, or stale required properties must fail closed. Never substitute a memorized broker specification or force the minimum lot. If the minimum permitted volume risks more than the configured cash risk budget, reject the trade.

Netting and hedging are distinct account capabilities. Opposing same-symbol positions are valid only when the terminal confirms retail hedging and the account-wide portfolio/risk/ledger checks admit the additional exposure. Do not simulate independent hedged tickets on a netting account.

## Costs and timestamps

Every evidence bundle must identify the actual broker/server, account currency, instrument specification, fill mode, spread source, commission schedule, swaps/financing, fees, and slippage assumptions. Historical data vendor and execution broker are separate fields: they may be the same or different.

Raw MT5 deal timestamps use broker-server time. Never label them UTC by appending Z or applying today's offset to an entire historical interval. UTC normalization requires a verified historical server-time mapping for the tested interval, including daylight-saving transitions. Missing mapping blocks UTC-based comparisons; it must not be guessed.

## Release gates

1. Compile the exact EA and indicator source revision with MetaEditor; preserve compiler output and build identity.
2. Run matched historical Strategy Tester variants on the same data, inputs, terminal build, balance, leverage, and cost model, with a locked chronological out-of-sample window.
3. Reconcile native deal history, orders, positions, partial fills/closes, commissions, swaps, fees, and realized P&L to the execution ledger.
4. Verify reconnect, ambiguous acknowledgement, duplicate submission, partial execution, restart/recovery, stop modification, emergency stop, and database/ledger outage behavior on demo.
5. Confirm that invalid geometry, unknown contract values, insufficient margin, volume normalization, stale quotes, ledger unavailability, and risk-limit breaches reject new entries without bypass.
6. Keep live execution blocked until the exact candidate passes all software, data-quality, account/symbol, reconciliation, and operational gates.

Passing repository CI proves only the checks actually executed by CI. It does not prove terminal compilation unless MetaEditor ran, broker execution unless a demo account was exercised, or profitability without cost-inclusive locked-OOS evidence.

## Provider independence tests

The test matrix must use at least two materially different MT5 server configurations before describing provider portability as validated. Include distinct symbol suffixes/specifications, account currencies, commission/spread structures, and one netting-versus-hedging contrast where available. This is a portability matrix, not permission to execute live or to weaken risk controls.