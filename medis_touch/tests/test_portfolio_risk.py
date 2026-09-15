import pytest
from medis_touch.app.portfolio_risk import PortfolioExposure, assess_portfolio


def test_portfolio_rejects_single_symbol_concentration():
    result = assess_portfolio((PortfolioExposure("EURUSD", 80), PortfolioExposure("XAUUSD", 20)), max_gross_notional=200, max_concentration_ratio=0.75)
    assert not result.allowed
    assert "CONCENTRATION_LIMIT" in result.reasons


def test_portfolio_accounts_for_correlation():
    exposures = (PortfolioExposure("EURUSD", 50), PortfolioExposure("GBPUSD", 50))
    result = assess_portfolio(exposures, max_gross_notional=200, max_concentration_ratio=1.0, max_correlated_risk=100, correlation_matrix={("EURUSD", "GBPUSD"): 0.9})
    assert not result.allowed
    assert "CORRELATED_RISK_LIMIT" in result.reasons


def test_factor_exposure_is_aggregated():
    result = assess_portfolio((PortfolioExposure("EURUSD", 50, (("USD", -1),)), PortfolioExposure("GBPUSD", 50, (("USD", -1),))), max_gross_notional=200, max_concentration_ratio=1.0)
    assert dict(result.net_factor_exposure)["USD"] == pytest.approx(-100)
