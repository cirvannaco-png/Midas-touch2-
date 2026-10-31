# Broker-neutral MetaTrader 5 compatibility contract

## Scope

Midas Touch supports broker selection through the MetaTrader 5 terminal. It does not maintain a hard-coded list of preferred or approved broker brands. The operator may connect any broker that provides an MT5 trading account and exposes the required symbols and execution capabilities through the terminal.

This is not a claim of compatibility with non-MT5 venues or proprietary APIs. Supporting a non-MT5 venue requires a separate execution adapter and its own contract tests.

## Runtime capability checks

The EA must validate the connected account and actual symbol metadata at runtime. Do not infer capability from a broker name, marketing label, symbol alias, or prior test with another provider.

For every chart symbol and order path, validate at least:

- Terminal and trade-server connectivity.
- Actual symbol name/visibility, quote freshness, bid/ask, point size, digits, tick size, tick value, contract size and calculation mode.
- Trade mode (disabled, close-only, long-only, short-only or full access) and current trading session.
- Minimum, maximum and step volume; normalize down only and reject any broker minimum that exceeds the selected risk budget.
- Execution and order-filling modes supported by the symbol; select filling from that symbol's terminal metadata.
- Stop and freeze distances, price-grid alignment, and whether protective SL/TP changes are currently admissible.
- Account currency, leverage, free margin, equity, balance, and margin mode (netting, exchange or retail hedging).
- Actual commission, swap/financing, spread and slippage evidence for the selected account when building cost-inclusive tests.

When a property is missing, non-finite, contradictory, stale or unsupported, fail closed for new exposure. Continue safe management and reconciliation of existing positions where the terminal still permits it.

## Operator-selected broker validation

Before enabling execution on a newly selected broker:

1. Record the broker server label, terminal build, account currency, leverage, margin mode, and exact symbol names/specifications. Redact account identifiers and all credentials.
2. Compile the exact candidate and preserve its source commit, EX5 hash, `.set` file, and MetaEditor log.
3. Run matched Strategy Tester cases with the selected broker's history and actual spread/commission/swap assumptions. Keep a separate, untouched locked-OOS window.
4. On that broker's demo account, exercise order entry/rejection, partial fills and closes, duplicate/ambiguous acknowledgements, stop modification, restart recovery, position/deal reconciliation, ledger authorization, and emergency stop.
5. Retain sanitized reports, deal exports, configuration fingerprints, and UTC timestamps. Mark unexercised scenarios BLOCKED, not PASS.

A pass on one broker/account/symbol specification does not certify a different broker, server, account type, or symbol contract. Broker selection is open; validation remains specific to the selected environment.

## Account-mode boundary

Independent opposite-direction positions on the same symbol require an MT5 retail-hedging account. Netting and exchange accounts aggregate exposure and must remain fail-closed against claims of two independent same-symbol positions. This is a platform/account capability, not a broker-brand rule.
