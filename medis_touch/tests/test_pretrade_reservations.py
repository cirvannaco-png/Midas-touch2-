# ruff: noqa: I001

from concurrent.futures import ThreadPoolExecutor
from tempfile import NamedTemporaryFile

import pytest

from medis_touch.app.pretrade_risk import PreTradeLimits, PersistentPortfolioAdmission, RiskReservationBook


def _limits() -> PreTradeLimits:
    return PreTradeLimits(1000, 1000, 600, 100, 5)


def _reserve(book: RiskReservationBook, reservation_id: str, *, ttl_seconds: float | None = 30.0):
    return book.reserve(reservation_id, portfolio_notional=0, symbol_notionals={}, requested_portfolio_notional=300, requested_symbol_notionals={"XAUUSD": 300}, limits=_limits(), ttl_seconds=ttl_seconds)


def test_reservation_book_accumulates_portfolio_and_symbol_capacity() -> None:
    book = RiskReservationBook()
    _reserve(book, "r1")
    _reserve(book, "r2")
    assert len(book.snapshot()) == 2


def test_reservation_book_rejects_aggregate_portfolio_oversubscription() -> None:
    book = RiskReservationBook()
    portfolio_only_limits = PreTradeLimits(1000, 1000, 1000, 100, 5)
    book.reserve("r1", portfolio_notional=0, symbol_notionals={}, requested_portfolio_notional=700, requested_symbol_notionals={"XAUUSD": 700}, limits=portfolio_only_limits)
    with pytest.raises(PermissionError, match="portfolio exposure reservation limit"):
        book.reserve("r2", portfolio_notional=0, symbol_notionals={}, requested_portfolio_notional=400, requested_symbol_notionals={"EURUSD": 400}, limits=portfolio_only_limits)


def test_reservation_book_rejects_aggregate_symbol_oversubscription() -> None:
    book = RiskReservationBook()
    _reserve(book, "r1")
    with pytest.raises(PermissionError, match="symbol exposure reservation limit: XAUUSD"):
        book.reserve("r2", portfolio_notional=0, symbol_notionals={}, requested_portfolio_notional=200, requested_symbol_notionals={"XAUUSD": 400}, limits=_limits())


def test_reservation_is_idempotent_and_release_restores_capacity() -> None:
    book = RiskReservationBook()
    first = _reserve(book, "same")
    second = _reserve(book, "same")
    assert first == second
    book.release("same")
    assert book.snapshot() == ()


def test_conflicting_reservation_identity_is_rejected() -> None:
    book = RiskReservationBook()
    _reserve(book, "same")
    with pytest.raises(ValueError, match="different exposure identity"):
        book.reserve("same", portfolio_notional=0, symbol_notionals={}, requested_portfolio_notional=400, requested_symbol_notionals={"EURUSD": 400}, limits=_limits())


def test_reservation_consume_releases_only_after_authoritative_commit() -> None:
    book = RiskReservationBook()
    _reserve(book, "consume-me")
    book.consume("consume-me")
    assert book.snapshot() == ()


def test_reservation_expiry_is_deterministic() -> None:
    book = RiskReservationBook()
    reservation = _reserve(book, "expires", ttl_seconds=30)
    assert book.expire(now=reservation.expires_at) == ("expires",)
    assert book.snapshot() == ()


def test_reservation_rejects_non_finite_or_negative_inputs() -> None:
    book = RiskReservationBook()
    with pytest.raises(ValueError):
        book.reserve("bad", portfolio_notional=0, symbol_notionals={}, requested_portfolio_notional=float("nan"), requested_symbol_notionals={"XAUUSD": 1}, limits=_limits())
    with pytest.raises(ValueError):
        book.reserve("bad-negative", portfolio_notional=0, symbol_notionals={}, requested_portfolio_notional=1, requested_symbol_notionals={"XAUUSD": -1}, limits=_limits())
    with pytest.raises(ValueError):
        book.reserve("bad-ttl", portfolio_notional=0, symbol_notionals={}, requested_portfolio_notional=1, requested_symbol_notionals={"XAUUSD": 1}, limits=_limits(), ttl_seconds=0)


def test_persistent_admission_commits_reservation_and_exposure_atomically() -> None:
    with NamedTemporaryFile(suffix=".db") as file:
        admission = PersistentPortfolioAdmission(file.name)
        reservation = admission.reserve("r1", scope_id="acct", requested_portfolio_notional=300, requested_symbol_notionals={"XAUUSD": 300}, limits=_limits())
        assert admission.snapshot("acct") == (reservation,)
        admission.commit("r1")
        assert admission.snapshot("acct") == ()
        with pytest.raises(PermissionError):
            admission.reserve("r2", scope_id="acct", requested_portfolio_notional=800, requested_symbol_notionals={"XAUUSD": 800}, limits=_limits())


def test_persistent_admission_serializes_concurrent_reservations_without_oversubscription() -> None:
    with NamedTemporaryFile(suffix=".db") as file:
        admission = PersistentPortfolioAdmission(file.name)

        def attempt(index: int) -> bool:
            try:
                admission.reserve(f"r{index}", scope_id="acct", requested_portfolio_notional=600, requested_symbol_notionals={"XAUUSD": 600}, limits=_limits(), ttl_seconds=60)
                return True
            except PermissionError:
                return False

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(8)))
        assert sum(results) == 1
        assert len(admission.snapshot("acct")) == 1
