# Medis Touch VPS Runtime Contract

The VPS is the persistent execution host for the MT5 terminal and Medis Touch EA. It is not an entitlement authority and it must not bypass backend execution gates.

## Runtime components

1. Windows VPS
2. MetaTrader 5 terminal
3. Medis Touch EA
4. Broker connection
5. Secure backend/API connection

## Startup contract

After VPS reboot or MT5 restart:

- start MT5
- confirm broker connection
- confirm the expected account/environment
- confirm the EA is attached to the intended chart/symbol
- confirm EA initialization succeeds
- confirm backend authentication succeeds
- reconcile broker positions before permitting new execution
- report health only after reconciliation is complete

## Failure contract

Any failed prerequisite blocks new execution. Recovery may reconnect or restart the terminal, but must not manufacture authorization or assume that a prior in-memory portfolio state is authoritative.

## Watchdog requirements

The eventual VPS watchdog should monitor:

- MT5 process liveness
- broker connection state
- EA heartbeat/last-seen timestamp
- backend connectivity
- terminal/EA error conditions
- position reconciliation status
- execution acknowledgement latency

Restart/reconnect actions must be bounded and auditable. Repeated failure must escalate rather than loop indefinitely.

## Security contract

- broker credentials stay inside the MT5/broker runtime boundary
- backend secrets are stored in the VPS secret store/environment, never committed
- API authentication is separate from subscriber copy-feed credentials
- logs must not contain credentials, API keys, copy keys, or payment secrets
- remote administration must use a secured administrative channel

## Execution boundary

The EA must continue to enforce the canonical fail-closed chain:

`SIGNAL -> Freshness -> Eligibility -> Entitlement -> Explicit Copy Authorization -> Broker Capability -> User Risk Validation -> Risk Gate -> Portfolio Gate -> Persistent Portfolio Admission -> Execution Ledger -> OrderCheck -> OrderSendAsync -> Broker Acknowledgement -> OnTradeTransaction -> Position Observation -> Reconciliation -> Outcome Telemetry`

A VPS being online is never evidence that a trade is authorized.

## Production gate

This contract is documentation only until a real VPS is provisioned and the MT5/EA/backend/broker path is tested end-to-end. No repository change should represent an unverified VPS as live.
