"""Fail-closed execution validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite


class RejectionReason(str, Enum):
    MISSING_POINT_SIZE = "MISSING_POINT_SIZE"
    MISSING_TICK_SIZE = "MISSING_TICK_SIZE"
    MISSING_STOPS_LEVEL = "MISSING_STOPS_LEVEL"
    MISSING_FREEZE_LEVEL = "MISSING_FREEZE_LEVEL"
    MISSING_VOLUME_LIMITS = "MISSING_VOLUME_LIMITS"
    STOP_DISTANCE_TOO_TIGHT = "STOP_DISTANCE_TOO_TIGHT"
    FREEZE_DISTANCE_TOO_TIGHT = "FREEZE_DISTANCE_TOO_TIGHT"
    PRICE_NOT_NORMALIZED = "PRICE_NOT_NORMALIZED"
    INSUFFICIENT_MARGIN = "INSUFFICIENT_MARGIN"
    TRADING_NOT_PERMITTED = "TRADING_NOT_PERMITTED"
    SESSION_CLOSED = "SESSION_CLOSED"
    VOLUME_OUT_OF_RANGE = "VOLUME_OUT_OF_RANGE"


@dataclass(frozen=True)
class SymbolMetadata:
    point_size: float | None
    tick_size: float | None
    stops_level_points: int | None
    freeze_level_points: int | None
    volume_min: float | None
    volume_max: float | None
    volume_step: float | None
    trading_permitted: bool | None
    session_open: bool | None
    price_digits: int | None


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: RejectionReason | None = None
    detail: str = ""

    @staticmethod
    def reject(reason: RejectionReason, detail: str = "") -> ValidationResult:
        return ValidationResult(ok=False, reason=reason, detail=detail)

    @staticmethod
    def accept() -> ValidationResult:
        return ValidationResult(ok=True)


def validate_stop_distance(*, entry_price: float, stop_loss: float, meta: SymbolMetadata) -> ValidationResult:
    if meta.point_size is None:
        return ValidationResult.reject(RejectionReason.MISSING_POINT_SIZE)
    if not isfinite(meta.point_size) or meta.point_size <= 0:
        return ValidationResult.reject(RejectionReason.MISSING_POINT_SIZE, "point_size must be finite and > 0")
    if meta.stops_level_points is None:
        return ValidationResult.reject(RejectionReason.MISSING_STOPS_LEVEL)
    if meta.stops_level_points < 0:
        return ValidationResult.reject(RejectionReason.MISSING_STOPS_LEVEL, "stops_level_points < 0")
    if not all(isfinite(value) for value in (entry_price, stop_loss)):
        return ValidationResult.reject(RejectionReason.PRICE_NOT_NORMALIZED, "entry/stop price is not finite")
    distance_points = abs(entry_price - stop_loss) / meta.point_size
    if distance_points < meta.stops_level_points:
        return ValidationResult.reject(RejectionReason.STOP_DISTANCE_TOO_TIGHT, detail=f"{distance_points:.1f} points < required {meta.stops_level_points}")
    return ValidationResult.accept()


def validate_tick_size(price: float, meta: SymbolMetadata) -> ValidationResult:
    if meta.tick_size is None:
        return ValidationResult.reject(RejectionReason.MISSING_TICK_SIZE)
    if not isfinite(meta.tick_size) or meta.tick_size <= 0:
        return ValidationResult.reject(RejectionReason.MISSING_TICK_SIZE, "tick_size must be finite and > 0")
    if not isfinite(price):
        return ValidationResult.reject(RejectionReason.PRICE_NOT_NORMALIZED, "price is not finite")
    remainder = price % meta.tick_size
    if remainder > 1e-9 and (meta.tick_size - remainder) > 1e-9:
        return ValidationResult.reject(RejectionReason.PRICE_NOT_NORMALIZED, detail=f"{price} not aligned to tick_size {meta.tick_size}")
    return ValidationResult.accept()


def validate_freeze_level(*, entry_price: float, stop_loss: float, meta: SymbolMetadata) -> ValidationResult:
    if meta.point_size is None:
        return ValidationResult.reject(RejectionReason.MISSING_POINT_SIZE)
    if not isfinite(meta.point_size) or meta.point_size <= 0:
        return ValidationResult.reject(RejectionReason.MISSING_POINT_SIZE, "point_size must be finite and > 0")
    if meta.freeze_level_points is None:
        return ValidationResult.reject(RejectionReason.MISSING_FREEZE_LEVEL)
    if meta.freeze_level_points < 0:
        return ValidationResult.reject(RejectionReason.MISSING_FREEZE_LEVEL, "freeze_level_points < 0")
    if not all(isfinite(value) for value in (entry_price, stop_loss)):
        return ValidationResult.reject(RejectionReason.PRICE_NOT_NORMALIZED, "entry/stop price is not finite")
    distance_points = abs(entry_price - stop_loss) / meta.point_size
    if distance_points < meta.freeze_level_points:
        return ValidationResult.reject(RejectionReason.FREEZE_DISTANCE_TOO_TIGHT, detail=f"{distance_points:.1f} points < freeze level {meta.freeze_level_points}")
    return ValidationResult.accept()


def validate_price_normalization(price: float, meta: SymbolMetadata) -> ValidationResult:
    if meta.price_digits is None:
        return ValidationResult.reject(RejectionReason.PRICE_NOT_NORMALIZED, "digits unknown")
    if meta.price_digits < 0 or not isfinite(price):
        return ValidationResult.reject(RejectionReason.PRICE_NOT_NORMALIZED, "invalid price metadata or value")
    rounded = round(price, meta.price_digits)
    if abs(rounded - price) > 1e-12:
        return ValidationResult.reject(RejectionReason.PRICE_NOT_NORMALIZED, detail=f"{price} not aligned to {meta.price_digits} digits")
    return ValidationResult.accept()


def validate_volume(volume: float, meta: SymbolMetadata) -> ValidationResult:
    if meta.volume_min is None or meta.volume_max is None or meta.volume_step is None:
        return ValidationResult.reject(RejectionReason.MISSING_VOLUME_LIMITS)
    if not all(isfinite(value) for value in (volume, meta.volume_min, meta.volume_max, meta.volume_step)) or meta.volume_step <= 0:
        return ValidationResult.reject(RejectionReason.MISSING_VOLUME_LIMITS, "volume metadata must be finite and step > 0")
    if meta.volume_min < 0 or meta.volume_max < meta.volume_min:
        return ValidationResult.reject(RejectionReason.MISSING_VOLUME_LIMITS, "invalid volume range")
    if not meta.volume_min <= volume <= meta.volume_max:
        return ValidationResult.reject(RejectionReason.VOLUME_OUT_OF_RANGE)
    steps = (volume - meta.volume_min) / meta.volume_step
    if abs(steps - round(steps)) > 1e-6:
        return ValidationResult.reject(RejectionReason.VOLUME_OUT_OF_RANGE, detail="not aligned to volume_step")
    return ValidationResult.accept()


def validate_trading_permissions(meta: SymbolMetadata) -> ValidationResult:
    if meta.trading_permitted is None or meta.trading_permitted is False:
        return ValidationResult.reject(RejectionReason.TRADING_NOT_PERMITTED)
    if meta.session_open is None or meta.session_open is False:
        return ValidationResult.reject(RejectionReason.SESSION_CLOSED)
    return ValidationResult.accept()


def validate_margin(required_margin: float | None, free_margin: float | None) -> ValidationResult:
    if required_margin is None or free_margin is None:
        return ValidationResult.reject(RejectionReason.INSUFFICIENT_MARGIN, "margin data unavailable")
    if not all(isfinite(value) for value in (required_margin, free_margin)) or required_margin < 0 or free_margin < 0:
        return ValidationResult.reject(RejectionReason.INSUFFICIENT_MARGIN, "invalid margin data")
    if required_margin > free_margin:
        return ValidationResult.reject(RejectionReason.INSUFFICIENT_MARGIN)
    return ValidationResult.accept()


def validate_execution(*, entry_price: float, stop_loss: float, volume: float, meta: SymbolMetadata, required_margin: float | None, free_margin: float | None) -> ValidationResult:
    for result in (
        validate_stop_distance(entry_price=entry_price, stop_loss=stop_loss, meta=meta),
        validate_freeze_level(entry_price=entry_price, stop_loss=stop_loss, meta=meta),
        validate_tick_size(entry_price, meta),
        validate_price_normalization(entry_price, meta),
        validate_volume(volume, meta),
        validate_trading_permissions(meta),
        validate_margin(required_margin, free_margin),
    ):
        if not result.ok:
            return result
    return ValidationResult.accept()
