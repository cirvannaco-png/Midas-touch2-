from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EA = ROOT / "EA" / "MedisTouch_v2.8.mq5"
BROKER = ROOT / "EA" / "includes" / "Execution" / "BrokerAdapter.mqh"
ORDERS = ROOT / "EA" / "includes" / "Execution" / "OrderManager.mqh"
RECOVERY = ROOT / "EA" / "includes" / "Recovery" / "RecoveryEngine.mqh"
POSITIONS = ROOT / "EA" / "includes" / "Execution" / "PositionManager.mqh"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def method_body(source: str, signature: str, next_signature: str) -> str:
    start = source.index(signature)
    end = source.index(next_signature, start)
    return source[start:end]


def test_broker_resolves_selectable_ticket_from_stable_position_identifier():
    source = read(BROKER)
    assert "ulong CBrokerAdapter::PositionTicketForIdentifier(string symbol,ulong positionIdentifier)" in source
    body = method_body(
        source,
        "ulong CBrokerAdapter::PositionTicketForIdentifier",
        "ulong CBrokerAdapter::ResolvePositionTicket",
    )
    assert "(ulong)PositionGetInteger(POSITION_IDENTIFIER)==positionIdentifier" in body
    assert "return ticket;" in body
    assert "POSITION_MAGIC)!=m_magic" in body


def test_order_manager_keeps_ticket_and_history_identity_as_separate_fields():
    source = read(ORDERS)
    assert "ulong                positionIdentifier;" in source
    assert "bool COrderManager::BindPositionIdentity(ulong knownTicket,ulong positionIdentifier,ulong positionTicket)" in source
    assert "long COrderManager::DecisionIdForPositionIdentifier(ulong positionIdentifier)" in source

    body = method_body(
        source,
        "ulong COrderManager::PositionTicketAt",
        "long COrderManager::DecisionIdForPositionIdentifier",
    )
    assert "if(identifier==0) return 0;" in body
    assert "(ulong)PositionGetInteger(POSITION_IDENTIFIER)==identifier" in body
    assert "m_trades[idx].fsm.SetTicket(actualTicket);" in body


def test_position_manager_requires_resolved_ticket_before_managing_stops():
    source = read(POSITIONS)
    assert "ulong ticket=m_orders.PositionTicketAt(i);" in source
    assert "if(ticket==0) continue;" in source


def test_restart_recovery_restores_both_ticket_and_position_identity():
    source = read(RECOVERY)
    assert "ulong positionIdentifier=(ulong)PositionGetInteger(POSITION_IDENTIFIER);" in source
    assert "m_orders.BindPositionIdentity(ticket,positionIdentifier,ticket);" in source


def test_trade_transaction_maps_entries_and_exits_by_position_identifier():
    source = read(EA)
    assert "g_broker.PositionTicketForIdentifier(_Symbol,positionIdentifier)" in source
    assert "g_orders.BindPositionIdentity(orderTicket,positionIdentifier,positionTicket);" in source
    assert "g_orders.DecisionIdForPositionIdentifier(positionIdentifier)" in source
    assert "if(decisionId<=0) decisionId=g_orders.DecisionIdForTicket(positionIdentifier);" in source
