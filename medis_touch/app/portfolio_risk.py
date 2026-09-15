"""Portfolio-level concentration and correlation controls.

The functions are deterministic and dependency-free so the risk layer can run
on the current Render Free footprint. They do not invent alpha; they constrain
aggregate exposure created by multiple simultaneous trades.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt


@dataclass(frozen=True)
class PortfolioExposure:
    symbol: str
    notional: float
    factor_exposures: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class PortfolioRiskResult:
    allowed: bool
    gross_notional: float
    net_factor_exposure: tuple[tuple[str, float], ...]
    concentration_ratio: float
    correlated_risk: float
    reasons: tuple[str, ...] = ()


def _validate(exposures: tuple[PortfolioExposure, ...]) -> None:
    for exposure in exposures:
        if not exposure.symbol:
            raise ValueError("symbol is required")
        if not isfinite(exposure.notional) or exposure.notional < 0:
            raise ValueError("notional must be finite and non-negative")
        for factor, value in exposure.factor_exposures:
            if not factor or not isfinite(value):
                raise ValueError("factor exposure must be named and finite")


def assess_portfolio(exposures: tuple[PortfolioExposure, ...], *, max_gross_notional: float, max_concentration_ratio: float = 0.35, max_correlated_risk: float | None = None, correlation_matrix: dict[tuple[str, str], float] | None = None) -> PortfolioRiskResult:
    _validate(exposures)
    if not isfinite(max_gross_notional) or max_gross_notional < 0:
        raise ValueError("max_gross_notional must be finite and non-negative")
    if not 0 < max_concentration_ratio <= 1:
        raise ValueError("max_concentration_ratio must be in (0, 1]")
    if max_correlated_risk is not None and (not isfinite(max_correlated_risk) or max_correlated_risk < 0):
        raise ValueError("max_correlated_risk must be finite and non-negative")

    gross = sum(item.notional for item in exposures)
    largest = max((item.notional for item in exposures), default=0.0)
    concentration = largest / gross if gross else 0.0

    factors: dict[str, float] = {}
    for item in exposures:
        for factor, value in item.factor_exposures:
            factors[factor] = factors.get(factor, 0.0) + value * item.notional
    factor_vector = tuple(sorted(factors.items()))

    correlated = 0.0
    matrix = correlation_matrix or {}
    for left in exposures:
        for right in exposures:
            if left.symbol == right.symbol:
                correlation = 1.0
            else:
                correlation = matrix.get((left.symbol, right.symbol), matrix.get((right.symbol, left.symbol), 0.0))
            if not isfinite(correlation) or not -1.0 <= correlation <= 1.0:
                raise ValueError("correlations must be finite and in [-1, 1]")
            correlated += left.notional * right.notional * correlation
    correlated_risk = sqrt(max(0.0, correlated))

    reasons: list[str] = []
    if gross > max_gross_notional:
        reasons.append("GROSS_NOTIONAL_LIMIT")
    if concentration > max_concentration_ratio:
        reasons.append("CONCENTRATION_LIMIT")
    if max_correlated_risk is not None and correlated_risk > max_correlated_risk:
        reasons.append("CORRELATED_RISK_LIMIT")
    return PortfolioRiskResult(not reasons, gross, factor_vector, concentration, correlated_risk, tuple(reasons))
