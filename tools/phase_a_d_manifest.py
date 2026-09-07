"""Machine-readable architecture gates for the Medis Touch A-D program.

This validator is intentionally structural. It does not modify or interpret
trading decisions. A phase may only be promoted when its required artifacts
and protected boundaries are present; file existence alone is not treated as
proof of behavioral completion.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "telegram-bridge"
EA = ROOT / "EA"

REQUIRED_PHASE_A = (
    BRIDGE / "app/services/execution_guard.py",
    BRIDGE / "app/services/copy_authorization.py",
    BRIDGE / "app/services/payment_integrity.py",
    EA / "includes/Portfolio/PortfolioManager.mqh",
    EA / "includes/Portfolio/RiskGuard.mqh",
)

PHASE_B_TARGETS = (
    BRIDGE / "app/api/signals.py",
    BRIDGE / "app/api/trades.py",
    BRIDGE / "app/api/outcomes.py",
    BRIDGE / "app/api/webhook.py",
    BRIDGE / "app/api/admin.py",
)

PHASE_D_TARGETS = (
    BRIDGE / "app/domain_models/base_types.py",
    BRIDGE / "app/domain_models/settings.py",
    BRIDGE / "app/domain_models/signals.py",
    BRIDGE / "app/domain_models/trades.py",
    BRIDGE / "app/domain_models/outcomes.py",
    BRIDGE / "app/domain_models/calibration.py",
    BRIDGE / "app/domain_models/subscriptions.py",
    BRIDGE / "app/domain_models/payments.py",
)

CANONICAL_GATE_ORDER = (
    "signal",
    "freshness",
    "eligibility",
    "entitlement",
    "copy_authorization",
    "broker_capability",
    "user_risk_validation",
    "risk_gate",
    "portfolio_gate",
    "persistent_portfolio_admission",
    "execution_ledger",
    "order_check",
    "order_send_async",
    "broker_acknowledgement",
    "trade_transaction",
    "position_observation",
    "reconciliation",
    "outcome_telemetry",
)


def main() -> int:
    missing_a = [str(p.relative_to(ROOT)) for p in REQUIRED_PHASE_A if not p.exists()]
    if missing_a:
        raise SystemExit("Phase A structural gate failed: " + ", ".join(missing_a))

    # Phase B/D are intentionally reported as pending until the real
    # decomposition lands. This prevents CI from confusing scaffolding with
    # completion and makes the promotion gate explicit.
    missing_b = [str(p.relative_to(ROOT)) for p in PHASE_B_TARGETS if not p.exists()]
    missing_d = [str(p.relative_to(ROOT)) for p in PHASE_D_TARGETS if not p.exists()]

    print("Phase A: structurally present")
    print("Phase B: pending" if missing_b else "Phase B: targets present; behavioral tests still required")
    print("Phase D: pending" if missing_d else "Phase D: targets present; compatibility tests still required")
    print("Canonical execution gates:")
    print(" -> ".join(CANONICAL_GATE_ORDER))
    return 0


if __name__ == "__main__":
    main()
