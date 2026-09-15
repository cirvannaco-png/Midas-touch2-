import pytest

from medis_touch.app.pretrade_risk import PreTradeLimits, RiskReservationBook


def _limits() -> PreTradeLimits:
    return PreTradeLimits(1000, 1000, 600, 100, 5)


def test_reservation_book_accumulates_portfolio_and_symbol_capacity() -> None:
    book = RiskReservationBook()
    book.reserve(
        "r1", portfolio_notional=0, symbol_notionals={},
        requested_portfolio_notional=400, requested_symbol_notionals={"XAUUSD": 400}, limits=_limits(),
    )
    book.reserve(
        "r2", portfolio_notional=0, symbol_notionals={},
        requested_portfolio_notional=300, requested_symbol_notionals={"EURUSD": 300}, limits=_limits(),
    )
    assert len(book.snapshot()) == 2


def test_reservation_book_rejects_aggregate_portfolio_oversubscription() -> None:
    book = RiskReservationBook()
    book.reserve(
        "r1", portfolio_notional=0, symbol_notionals={},
        requested_portfolio_notional=700, requested_symbol_notionals={"XAUUSD": 700}, limits=_limits(),
    )
    with pytest.raises(PermissionError, match="portfolio exposure reservation limit"):
        book.reserve(
            "r2", portfolio_notional=0, symbol_notionals={},
            requested_portfolio_notional=400, requested_symbol_notionals={"EURUSD": 400}, limits=_limits(),
        )


def test_reservation_book_rejects_aggregate_symbol_oversubscription() -> None:
    book = RiskReservationBook()
    book.reserve(
        "r1", portfolio_notional=0, symbol_notionals={},
        requested_portfolio_notional=300, requested_symbol_notionals={"XAUUSD": 300}, limits=_limits(),
    )
    with pytest.raises(PermissionError, match="symbol exposure reservation limit: XAUUSD"):
        book.reserve(
            "r2", portfolio_notional=0, symbol_notionals={},
            requested_portfolio_notional=200, requested_symbol_notionals={"XAUUSD": 400}, limits=_limits(),
        )


def test_reservation_is_idempotent_and_release_restores_capacity() -> None:
    book = RiskReservationBook()
    first = book.reserve(
        "same", portfolio_notional=0, symbol_notionals={},
        requested_portfolio_notional=500, requested_symbol_notionals={"XAUUSD": 500}, limits=_limits(),
    )
    second = book.reserve(
        "same", portfolio_notional=0, symbol_notionals={},
        requested_portfolio_notional=500, requested_symbol_notionals={"XAUUSD": 500}, limits=_limits(),
    )
    assert first == second
    book.release("same")
    assert book.snapshot() == ()


def test_reservation_rejects_non_finite_or_negative_inputs() -> None:
    book = RiskReservationBook()
    with pytest.raises(ValueError):
        book.reserve(
            "bad", portfolio_notional=0, symbol_notionals={},
            requested_portfolio_notional=float("nan"), requested_symbol_notionals={"XAUUSD": 1}, limits=_limits(),
        )
    with pytest.raises(ValueError):
        book.reserve(
            "bad-negative", portfolio_notional=0, symbol_notionals={},
            requested_portfolio_notional=1, requested_symbol_notionals={"XAUUSD": -1}, limits=_limits(),
        )
