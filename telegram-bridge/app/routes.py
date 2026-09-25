import asyncio
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from tools.decision_fingerprint import canonical_serialize, fingerprint

from app import bot as bot_module
from app.config import APP_VERSION, settings
from app.copy_trading import can_copy
from app.database import check_db_connection, get_session
from app.formatter import format_lifecycle_banner, format_signal_message, format_trade_message
from app.logger import logger
from app.models import (
    ApprovedWeightVersion,
    Signal,
    SignalDeliveryOutbox,
    SignalLifecycleStatus,
    SignalOutcome,
    SignalStatus,
    TradeEvent,
    TradeEventStatus,
    TradeEventType,
)
from app.ratelimit import enforce_rate_limit
from app.settings_store import get_signal_broadcast_controls
from app.subscriptions import get_subscriber_by_copy_feed_key
from app.telegram import NonRetryableError, edit_telegram_message, send_telegram_message
from app.utils import measure_latency
from app.validator import validate_signal, validate_trade_event

router = APIRouter()

VALID_TIMEFRAMES = {"M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN"}

def canonical_decision_payload(payload: "SignalRequest") -> dict:
    data = payload.model_dump(by_alias=True)
    data["schema_version"] = data.get("decision_schema_version")
    data["action"] = data.get("policy_action")
    data["session"] = data.get("session") or ""
    return data



# ---------- Request/Response Schemas ----------
class SignalRequest(BaseModel):
    signal_id: str = Field(..., min_length=1, max_length=100)
    symbol: str = Field(..., min_length=1, max_length=20)
    direction: Literal["BUY", "SELL"]
    entry: float = Field(..., gt=0)
    # Canonical TradeSetup fields. Thesis invalidation is deliberately
    # distinct from the broker protective stop, and final_tp is distinct
    # from the runner's intermediate targets. Both are optional so older
    # EA builds remain wire-compatible while newer builds retain the full
    # setup contract instead of silently losing these fields in Pydantic.
    invalidation: float | None = Field(default=None, gt=0)
    sl: float = Field(..., gt=0)
    tp1: float = Field(..., gt=0)
    tp2: float = Field(..., gt=0)
    final_tp: float | None = Field(default=None, gt=0)
    confidence: int = Field(..., ge=0, le=100)
    reasons: list[str] = Field(..., min_length=1)
    timeframe: str
    strategy: str | None = Field(default=None, max_length=64)
    decision_schema_version: str | None = Field(default="decision-v1", max_length=64)
    strategy_version: str | None = Field(default=None, max_length=64)
    model_version: str | None = Field(default=None, max_length=64)
    calibration_version: str | None = Field(default=None, max_length=64)
    feature_schema_version: str | None = Field(default=None, max_length=64)
    environment_schema_version: str | None = Field(default=None, max_length=64)
    decision_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    policy_action: str | None = Field(default=None, max_length=32)
    reduce_risk: bool | None = Field(default=None)
    spread_points: float | None = Field(default=None)
    environment_key: str | None = Field(default=None, max_length=512)
    signal_time: datetime | None = None
    decision_time: datetime | None = None
    # v2.9: optional so pre-v2.9 EA builds keep working unmodified — see
    # models.py:Signal.extra. Not validated field-by-field on purpose;
    # this is display-only diagnostic data (sweep grade, BOS strength,
    # decay, chase distance, news risk, calibrated probability, pip
    # distances), never used for trading logic on the bridge side, so a
    # missing or malformed key degrades the Telegram card, not a decision.
    extra: dict | None = Field(default=None)
    # v2.11: promoted out of `extra` — see app/models.py:Signal for why.
    # All optional so a pre-v2.11 EA build's payload (no top-level tag
    # fields yet) still validates exactly as before; they just land NULL
    # and won't show up in tag-breakdown reports until the EA is rebuilt
    # against the new SignalPublisher payload.
    regime: str | None = Field(default=None, max_length=32)
    session_tag: str | None = Field(default=None, max_length=32, alias="session")
    sweep_grade: str | None = Field(default=None, max_length=16)
    htf_ob_aligned: bool | None = Field(default=None)
    weight_version: str | None = Field(default=None, max_length=64)

    model_config = {"populate_by_name": True}

    @field_validator("reasons")
    @classmethod
    def check_reason_lengths(cls, v):
        for i, reason in enumerate(v):
            if len(reason) > 200:
                raise ValueError(f"reason at index {i} too long (max 200)")
        return v

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v):
        if v not in VALID_TIMEFRAMES:
            raise ValueError(f"timeframe must be one of {sorted(VALID_TIMEFRAMES)}")
        return v


class BenchmarkSignalResponse(BaseModel):
    status: str
    processing_ms: float
    decision_fingerprint: str


class TradeEventRequest(BaseModel):
    event_id: str = Field(..., min_length=1, max_length=150)
    trade_id: str = Field(..., min_length=1, max_length=100)
    signal_id: str | None = Field(default=None, max_length=100)
    symbol: str = Field(..., min_length=1, max_length=20)
    direction: Literal["BUY", "SELL"]
    # Using the enum type directly keeps routes.py and models.py in sync
    # automatically — adding a new TradeEventType member covers it here too.
    # Pydantic v2 accepts the string value and coerces it to the enum instance.
    event: TradeEventType
    volume: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    sl: float | None = Field(default=None, gt=0)
    tp1: float | None = Field(default=None, gt=0)
    tp2: float | None = Field(default=None, gt=0)
    profit: float | None = None
    balance: float | None = Field(default=None, ge=0)
    equity: float | None = Field(default=None, ge=0)
    comment: str | None = Field(default=None, max_length=200)


class TradeEventResponse(BaseModel):
    status: str
    event_id: str
    trade_id: str
    duplicate: bool = False
    telegram_message_id: int | None = None


class OutcomeRequest(BaseModel):
    signal_id: str = Field(..., min_length=1, max_length=100)
    symbol: str = Field(..., min_length=1, max_length=20)
    direction: Literal["BUY", "SELL"]
    outcome: Literal["win", "loss", "scratch", "no_fill", "ambiguous"]
    realized_r: float | None = Field(default=None)
    mfe_r: float | None = Field(default=None)
    mae_r: float | None = Field(default=None)
    bars_held: int | None = Field(default=None, ge=0)
    bars_to_fill: int | None = Field(default=None, ge=0)
    filled: bool = Field(default=False)
    regime: str | None = Field(default=None, max_length=32)
    session_tag: str | None = Field(default=None, max_length=32, alias="session")
    sweep_grade: str | None = Field(default=None, max_length=16)
    htf_ob_aligned: bool | None = Field(default=None)
    strategy: str | None = Field(default=None, max_length=64)
    resolution: str | None = Field(default=None, max_length=64)
    commission_cost: float | None = Field(default=None, ge=0)
    spread_cost: float | None = Field(default=None, ge=0)
    slippage_cost: float | None = Field(default=None, ge=0)
    weight_version: str | None = Field(default=None, max_length=64)
    strategy_version: str | None = Field(default=None, max_length=64)
    model_version: str | None = Field(default=None, max_length=64)
    calibration_version: str | None = Field(default=None, max_length=64)
    feature_schema_version: str | None = Field(default=None, max_length=64)
    environment_schema_version: str | None = Field(default=None, max_length=64)
    decision_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    execution_time: datetime | None = None
    outcome_time: datetime | None = None
    confidence_at_signal: float | None = Field(default=None)
    confidence_decayed: float | None = Field(default=None)
    decay_bars: int | None = Field(default=None, ge=0)

    model_config = {"populate_by_name": True}


class OutcomeResponse(BaseModel):
    status: str
    signal_id: str
    upserted: bool = False


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str | None = None


class SignalResponse(BaseModel):
    status: str
    signal_id: str
    decision_fingerprint: str | None = None
    duplicate: bool = False
    telegram_message_id: int | None = None
    details: str | None = None


# ---------- Auth Dependency ----------
async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    if not secrets.compare_digest(x_api_key, settings.SECRET_KEY):
        logger.warning("Invalid API key attempt")
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


async def verify_benchmark_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    if not settings.BENCHMARK_ENABLED:
        raise HTTPException(status_code=404, detail="Benchmark route disabled")
    expected_key = settings.BENCHMARK_API_KEY or settings.SECRET_KEY
    if not secrets.compare_digest(x_api_key, expected_key):
        raise HTTPException(status_code=401, detail="Invalid benchmark API key")
    return True


# ---------- Endpoints ----------
@router.get("/", response_model=HealthResponse)
@router.head("/")
async def health_check():
    return {"status": "online", "version": APP_VERSION, "database": "not checked"}


@router.get("/health/db", response_model=HealthResponse)
async def health_db():
    db_ok = await check_db_connection()
    return {
        "status": "online" if db_ok else "degraded",
        "version": APP_VERSION,
        "database": "connected" if db_ok else "disconnected"
    }


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if not secrets.compare_digest(
        x_telegram_bot_api_secret_token or "", settings.WEBHOOK_SECRET_TOKEN
    ):
        logger.warning("Rejected Telegram webhook call with invalid secret token")
        raise HTTPException(status_code=401, detail="Invalid secret token")

    payload = await request.json()
    try:
        _chat = (payload.get("message") or payload.get("channel_post") or {}).get("chat") or {}
        _from = (payload.get("message") or {}).get("from") or {}
        logger.info(
            f"Telegram update from chat_id={_chat.get('id')} "
            f"type={_chat.get('type')} title={_chat.get('title')} "
            f"user_id={_from.get('id')}"
        )
    except AttributeError:
        logger.info("Telegram update with unexpected payload shape")

    try:
        await bot_module.process_update(payload)
    except Exception as e:
        logger.error(f"Failed to process Telegram update ({type(e).__name__}): {e}")

    return {"ok": True}


@router.post("/benchmark/signal", response_model=BenchmarkSignalResponse)
async def benchmark_signal(
    payload: SignalRequest,
    _auth: bool = Depends(verify_benchmark_api_key),
):
    """Read-only benchmark path: validate and fingerprint without DB or Telegram side effects."""
    start_time = time.perf_counter()
    valid, errors = validate_signal(payload.model_dump())
    if not valid:
        raise HTTPException(status_code=400, detail={"errors": errors})
    decision_payload = canonical_decision_payload(payload)
    expected_fingerprint = fingerprint(decision_payload)
    return BenchmarkSignalResponse(
        status="ok",
        processing_ms=round((time.perf_counter() - start_time) * 1000.0, 3),
        decision_fingerprint=expected_fingerprint,
    )


@router.post("/signal", response_model=SignalResponse)
async def receive_signal(
    request: Request,
    payload: SignalRequest,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
    _rate: None = Depends(enforce_rate_limit),
):
    start_time = time.time()
    log = logger.bind(signal_id=payload.signal_id)
    received_at = datetime.now(timezone.utc)
    log.info("Signal received")

    valid, errors = validate_signal(payload.model_dump())
    if not valid:
        raise HTTPException(status_code=400, detail={"signal_id": payload.signal_id, "errors": errors})

    decision_payload = canonical_decision_payload(payload)
    expected_fingerprint = fingerprint(decision_payload)
    claimed_fingerprint = (payload.decision_fingerprint or "").upper()
    parity_status = (
        "PARITY_OK"
        if claimed_fingerprint == expected_fingerprint
        else "PARITY_MISMATCH"
        if claimed_fingerprint
        else "FINGERPRINT_MISSING"
    )

    db_signal = Signal(
        signal_id=payload.signal_id,
        symbol=payload.symbol,
        direction=payload.direction,
        entry=payload.entry,
        invalidation=payload.invalidation,
        sl=payload.sl,
        tp1=payload.tp1,
        tp2=payload.tp2,
        final_tp=payload.final_tp,
        confidence=payload.confidence,
        reasons=payload.reasons,
        timeframe=payload.timeframe,
        strategy=payload.strategy,
        decision_schema_version=payload.decision_schema_version,
        strategy_version=payload.strategy_version,
        model_version=payload.model_version,
        calibration_version=payload.calibration_version,
        feature_schema_version=payload.feature_schema_version,
        environment_schema_version=payload.environment_schema_version,
        decision_fingerprint=claimed_fingerprint or None,
        canonical_decision=canonical_serialize(decision_payload),
        parity_status=parity_status,
        policy_action=payload.policy_action,
        reduce_risk=payload.reduce_risk,
        spread_points=payload.spread_points,
        environment_key=payload.environment_key,
        signal_time=payload.signal_time or payload.decision_time or received_at,
        decision_time=payload.decision_time or payload.signal_time or received_at,
        data_received_time=received_at,
        status=SignalStatus.PENDING if parity_status == "PARITY_OK" else SignalStatus.PERMANENTLY_FAILED,
        extra=payload.extra,
        regime=payload.regime,
        session=payload.session_tag,
        sweep_grade=payload.sweep_grade,
        htf_ob_aligned=payload.htf_ob_aligned,
        weight_version=payload.weight_version,
    )
    if parity_status != "PARITY_OK":
        db_signal.error_message = f"{parity_status}: expected {expected_fingerprint}, received {claimed_fingerprint or 'missing'}"

    session.add(db_signal)

    # Persist audit failures before returning an HTTP error. Valid signals
    # stay in one transaction through signal + outbox creation.
    if parity_status == "PARITY_MISMATCH" or (
        parity_status == "FINGERPRINT_MISSING" and settings.REQUIRE_DECISION_FINGERPRINT
    ):
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            log.info("Duplicate signal ignored (reservation lost)")
            return SignalResponse(
                status="duplicate",
                signal_id=payload.signal_id,
                decision_fingerprint=claimed_fingerprint or None,
                duplicate=True,
            )

        if parity_status == "PARITY_MISMATCH":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "PARITY_MISMATCH",
                    "signal_id": payload.signal_id,
                    "expected_fingerprint": expected_fingerprint,
                    "received_fingerprint": claimed_fingerprint,
                },
            )

        raise HTTPException(
            status_code=428,
            detail={
                "code": "FINGERPRINT_REQUIRED",
                "signal_id": payload.signal_id,
                "expected_fingerprint": expected_fingerprint,
                "received_fingerprint": None,
            },
        )

    # Keep the signal unflushed until the final commit so the valid path
    # writes the signal and durable outbox reservation atomically.
    with session.no_autoflush:
        broadcast_paused, muted_symbols = await get_signal_broadcast_controls(session)

    if broadcast_paused or payload.symbol.upper() in muted_symbols:
        db_signal.status = SignalStatus.ACTIVE
        db_signal.error_message = "Broadcast suppressed (paused or symbol muted)"
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            log.info("Duplicate signal ignored (reservation lost)")
            return SignalResponse(
                status="duplicate",
                signal_id=payload.signal_id,
                decision_fingerprint=expected_fingerprint,
                duplicate=True,
            )
        return SignalResponse(
            status="suppressed",
            signal_id=payload.signal_id,
            decision_fingerprint=expected_fingerprint,
            details="Broadcast paused or symbol muted - signal recorded, not sent to Telegram.",
        )

    message_payload = payload.model_dump(by_alias=True, mode="json")
    message_payload["decision_fingerprint"] = expected_fingerprint
    outbox = SignalDeliveryOutbox(
        signal_id=payload.signal_id,
        payload=message_payload,
        status="pending",
        attempts=0,
        next_attempt_at=received_at,
    )
    session.add(outbox)
    db_signal.status = SignalStatus.PENDING
    db_signal.latency_ms = measure_latency(start_time)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        log.info("Delivery outbox reservation lost for %s", payload.signal_id)
        return SignalResponse(
            status="duplicate",
            signal_id=payload.signal_id,
            decision_fingerprint=expected_fingerprint,
            duplicate=True,
        )
    return SignalResponse(
        status="queued",
        signal_id=payload.signal_id,
        decision_fingerprint=expected_fingerprint,
        details="Signal persisted; Telegram delivery queued asynchronously.",
    )



class LifecycleUpdateRequest(BaseModel):
    status: Literal["stale", "expired", "invalidated", "valid"]
    reason: str = Field(..., min_length=1, max_length=300)


class LifecycleUpdateResponse(BaseModel):
    signal_id: str
    lifecycle_status: str
    message_edited: bool


@router.patch("/signal/{signal_id}/status", response_model=LifecycleUpdateResponse)
async def update_signal_lifecycle(
    signal_id: str,
    payload: LifecycleUpdateRequest,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
):
    log = logger.bind(signal_id=signal_id)
    result = await session.execute(select(Signal).where(Signal.signal_id == signal_id))
    db_signal = result.scalar_one_or_none()
    if db_signal is None:
        raise HTTPException(status_code=404, detail=f"No signal found with signal_id={signal_id}")

    new_status = SignalLifecycleStatus(payload.status)
    edited = False
    if db_signal.telegram_message_id is not None and new_status != SignalLifecycleStatus.VALID:
        original_text = format_signal_message(
            {
                "signal_id": db_signal.signal_id,
                "symbol": db_signal.symbol,
                "direction": db_signal.direction,
                "entry": db_signal.entry,
                "invalidation": db_signal.invalidation,
                "sl": db_signal.sl,
                "tp1": db_signal.tp1,
                "tp2": db_signal.tp2,
                "final_tp": db_signal.final_tp,
                "strategy": db_signal.strategy,
                "timeframe": db_signal.timeframe,
                "confidence": db_signal.confidence,
                "reasons": db_signal.reasons,
                "extra": db_signal.extra,
                "decision_fingerprint": db_signal.decision_fingerprint,
            }
        )
        banner = format_lifecycle_banner(new_status.value, payload.reason)
        edited = await edit_telegram_message(db_signal.telegram_message_id, banner + "\n\n" + original_text)
        if not edited:
            log.warning(f"Lifecycle status DB-updated to {new_status.value} but Telegram edit failed")

    db_signal.lifecycle_status = new_status
    db_signal.lifecycle_reason = payload.reason
    db_signal.lifecycle_updated_at = datetime.now(timezone.utc)
    await session.commit()
    log.info(f"Lifecycle status -> {new_status.value}: {payload.reason}")

    return LifecycleUpdateResponse(signal_id=signal_id, lifecycle_status=new_status.value, message_edited=edited)


@router.post("/trade", response_model=TradeEventResponse)
async def receive_trade_event(
    request: Request,
    payload: TradeEventRequest,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
    _rate: None = Depends(enforce_rate_limit),
):
    start_time = time.time()
    log = logger.bind(event_id=payload.event_id, trade_id=payload.trade_id)
    log.info("Trade event received")

    valid, errors = validate_trade_event(payload.model_dump())
    if not valid:
        raise HTTPException(
            status_code=400,
            detail={"event_id": payload.event_id, "errors": errors}
        )

    db_event = TradeEvent(
        event_id=payload.event_id,
        trade_id=payload.trade_id,
        signal_id=payload.signal_id,
        symbol=payload.symbol,
        direction=payload.direction,
        event=payload.event,
        volume=payload.volume,
        price=payload.price,
        sl=payload.sl,
        tp1=payload.tp1,
        tp2=payload.tp2,
        profit=payload.profit,
        balance=payload.balance,
        equity=payload.equity,
        comment=payload.comment,
        status=TradeEventStatus.PENDING,
    )
    session.add(db_event)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        log.info("Duplicate trade event ignored (reservation lost)")
        return TradeEventResponse(
            status="duplicate", event_id=payload.event_id,
            trade_id=payload.trade_id, duplicate=True,
        )

    message_text = format_trade_message(payload.model_dump())
    try:
        msg_id = await send_telegram_message(message_text)
        status_event = TradeEventStatus.ACTIVE
        error_msg = None
    except NonRetryableError as e:
        log.error(f"Non-retryable failure: {e}")
        msg_id = None
        status_event = TradeEventStatus.PERMANENTLY_FAILED
        error_msg = str(e)
    except Exception as e:
        log.error(f"Sending failed after retries ({type(e).__name__}): {e}")
        msg_id = None
        status_event = TradeEventStatus.FAILED
        error_msg = str(e)

    latency = measure_latency(start_time)

    db_event.telegram_message_id = msg_id
    db_event.status = status_event
    db_event.error_message = error_msg
    db_event.latency_ms = latency
    await session.commit()

    if status_event in (TradeEventStatus.FAILED, TradeEventStatus.PERMANENTLY_FAILED):
        raise HTTPException(
            status_code=500,
            detail=f"Telegram sending failed. Trade event saved with status '{status_event.value}'."
        )

    return TradeEventResponse(
        status="sent", event_id=payload.event_id,
        trade_id=payload.trade_id, telegram_message_id=msg_id,
    )


async def retry_failed_trade_events_core(session: AsyncSession) -> dict:
    stale_before = datetime.now(timezone.utc) - timedelta(seconds=settings.PENDING_STALE_SECONDS)
    result = await session.execute(
        select(TradeEvent)
        .where(
            (TradeEvent.status == TradeEventStatus.FAILED)
            | ((TradeEvent.status == TradeEventStatus.PENDING) & (TradeEvent.received_at < stale_before))
        )
        .limit(5)
    )
    failed_events = result.scalars().all()
    if not failed_events:
        return {"message": "No failed trade events to retry."}

    retried_count = 0
    for db_event in failed_events:
        event_dict = {
            "event_id": db_event.event_id,
            "trade_id": db_event.trade_id,
            "signal_id": db_event.signal_id,
            "symbol": db_event.symbol,
            "direction": db_event.direction,
            "event": db_event.event.value,
            "volume": db_event.volume,
            "price": db_event.price,
            "sl": db_event.sl,
            "tp1": db_event.tp1,
            "tp2": db_event.tp2,
            "profit": db_event.profit,
            "balance": db_event.balance,
            "equity": db_event.equity,
            "comment": db_event.comment,
        }
        message_text = format_trade_message(event_dict)
        log = logger.bind(event_id=db_event.event_id, trade_id=db_event.trade_id)
        try:
            msg_id = await send_telegram_message(message_text)
            db_event.status = TradeEventStatus.ACTIVE
            db_event.telegram_message_id = msg_id
            db_event.error_message = None
            log.info("Retried trade event successfully")
            retried_count += 1
        except NonRetryableError as e:
            log.error(f"Permanent failure during retry: {e}")
            db_event.status = TradeEventStatus.PERMANENTLY_FAILED
            db_event.error_message = f"Retry failed permanently: {e}"
        except Exception as e:
            log.error(f"Retry failed ({type(e).__name__}): {e}")
            db_event.error_message = f"Retry failed: {e}"
        await session.commit()
        await asyncio.sleep(0.5)

    return {
        "message": f"Processed {len(failed_events)} failed trade events. Retried {retried_count} successfully.",
        "remaining_failed": len(failed_events) - retried_count
    }


@router.post("/outcome", response_model=OutcomeResponse)
async def receive_outcome(
    payload: OutcomeRequest,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
    _rate: None = Depends(enforce_rate_limit),
):
    log = logger.bind(signal_id=payload.signal_id)
    received_at = datetime.now(timezone.utc)

    existing = await session.scalar(
        select(SignalOutcome).where(SignalOutcome.signal_id == payload.signal_id)
    )
    upserted = existing is not None
    row = existing or SignalOutcome(signal_id=payload.signal_id)

    source_signal = await session.scalar(
        select(Signal).where(Signal.signal_id == payload.signal_id)
    )
    if source_signal is not None:
        row.signal_time = source_signal.signal_time or source_signal.received_at
        row.decision_time = source_signal.decision_time
        row.original_decision_fingerprint = source_signal.decision_fingerprint
        row.canonical_decision = source_signal.canonical_decision
        row.decision_fingerprint = payload.decision_fingerprint or source_signal.decision_fingerprint
        row.environment_key = source_signal.environment_key
        row.parity_status = (
            "PARITY_MISMATCH"
            if payload.decision_fingerprint
            and source_signal.decision_fingerprint
            and payload.decision_fingerprint.upper() != source_signal.decision_fingerprint.upper()
            else source_signal.parity_status or "FINGERPRINT_MISSING"
        )
        row.decision_schema_version = (source_signal.decision_schema_version if source_signal else None)
        row.strategy_version = payload.strategy_version or (source_signal.strategy_version if source_signal else None)
        row.model_version = payload.model_version or source_signal.model_version
        row.calibration_version = payload.calibration_version or source_signal.calibration_version
        row.feature_schema_version = payload.feature_schema_version or source_signal.feature_schema_version
        row.environment_schema_version = payload.environment_schema_version or source_signal.environment_schema_version
        row.weight_version = payload.weight_version or source_signal.weight_version
        row.data_received_time = received_at
    else:
        row.decision_fingerprint = payload.decision_fingerprint
        row.parity_status = "ORPHAN_SIGNAL"
        row.data_received_time = received_at
        row.decision_schema_version = "decision-v1"
        row.strategy_version = payload.strategy_version
        row.model_version = payload.model_version
        row.calibration_version = payload.calibration_version
        row.feature_schema_version = payload.feature_schema_version
        row.environment_schema_version = payload.environment_schema_version
        row.weight_version = payload.weight_version

    row.symbol = payload.symbol
    row.direction = payload.direction
    row.outcome = payload.outcome
    row.realized_r = payload.realized_r
    row.mfe_r = payload.mfe_r
    row.mae_r = payload.mae_r
    row.bars_held = payload.bars_held
    row.bars_to_fill = payload.bars_to_fill
    row.filled = payload.filled
    row.execution_time = payload.execution_time
    row.outcome_time = payload.outcome_time
    row.regime = payload.regime
    row.session = payload.session_tag
    row.sweep_grade = payload.sweep_grade
    row.htf_ob_aligned = payload.htf_ob_aligned
    row.strategy = payload.strategy or (source_signal.strategy if source_signal else None)
    row.resolution = payload.resolution
    row.commission_cost = payload.commission_cost
    row.spread_cost = payload.spread_cost
    row.slippage_cost = payload.slippage_cost
    row.confidence_at_signal = payload.confidence_at_signal
    row.confidence_decayed = payload.confidence_decayed
    row.decay_bars = payload.decay_bars

    if not upserted:
        session.add(row)
    await session.commit()

    if row.parity_status == "PARITY_MISMATCH":
        raise HTTPException(
            status_code=409,
            detail={"code": "PARITY_MISMATCH", "signal_id": payload.signal_id},
        )

    log.info(f"Outcome recorded: {payload.outcome}" + (" (updated)" if upserted else ""))
    return OutcomeResponse(status="ok", signal_id=payload.signal_id, upserted=upserted)


class ConfigResponse(BaseModel):
    symbol: str
    approved_weight_version: str | None
    approved_at: str | None
    params: dict | None = None


@router.get("/config/{symbol}", response_model=ConfigResponse)
async def get_config(
    symbol: str,
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
):
    latest = await session.scalar(
        select(ApprovedWeightVersion).order_by(ApprovedWeightVersion.approved_at.desc()).limit(1)
    )
    if latest is None:
        return ConfigResponse(symbol=symbol, approved_weight_version=None, approved_at=None, params=None)
    return ConfigResponse(
        symbol=symbol,
        approved_weight_version=latest.weight_version,
        approved_at=latest.approved_at.isoformat() if latest.approved_at else None,
        params=None,
    )


@router.post("/admin/run-cycle")
async def run_calibration_cycle(_auth: bool = Depends(verify_api_key)):
    from app.calibration import run_cycle
    result = await run_cycle()
    return result


@router.post("/trade/retry-failed")
async def retry_failed_trade_events(
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
    _rate: None = Depends(enforce_rate_limit),
):
    return await retry_failed_trade_events_core(session)


# ---------- Retry Failed Signals (core + HTTP endpoint) ----------
async def retry_failed_signals_core(session: AsyncSession) -> dict:
    stale_before = datetime.now(timezone.utc) - timedelta(seconds=settings.PENDING_STALE_SECONDS)
    result = await session.execute(
        select(Signal)
        .where(
            (Signal.status == SignalStatus.FAILED)
            | ((Signal.status == SignalStatus.PENDING) & (Signal.received_at < stale_before))
        )
        .limit(5)
    )
    failed_signals = result.scalars().all()
    if not failed_signals:
        return {"message": "No failed signals to retry."}

    retried_count = 0
    for db_signal in failed_signals:
        signal_dict = {
            "signal_id": db_signal.signal_id,
            "symbol": db_signal.symbol,
            "direction": db_signal.direction,
            "entry": db_signal.entry,
            "invalidation": db_signal.invalidation,
            "sl": db_signal.sl,
            "tp1": db_signal.tp1,
            "tp2": db_signal.tp2,
            "final_tp": db_signal.final_tp,
            "strategy": db_signal.strategy,
            "confidence": db_signal.confidence,
            "reasons": db_signal.reasons,
            "timeframe": db_signal.timeframe
        }
        message_text = format_signal_message(signal_dict)
        log = logger.bind(signal_id=db_signal.signal_id)
        try:
            msg_id = await send_telegram_message(message_text)
            db_signal.status = SignalStatus.ACTIVE
            db_signal.telegram_message_id = msg_id
            db_signal.error_message = None
            log.info("Retried signal successfully")
            retried_count += 1
        except NonRetryableError as e:
            log.error(f"Permanent failure during retry: {e}")
            db_signal.status = SignalStatus.PERMANENTLY_FAILED
            db_signal.error_message = f"Retry failed permanently: {e}"
        except Exception as e:
            log.error(f"Retry failed ({type(e).__name__}): {e}")
            db_signal.error_message = f"Retry failed: {e}"
        await session.commit()
        await asyncio.sleep(0.5)

    return {
        "message": f"Processed {len(failed_signals)} failed signals. Retried {retried_count} successfully.",
        "remaining_failed": len(failed_signals) - retried_count
    }


@router.post("/retry-failed")
async def retry_failed_signals(
    session: AsyncSession = Depends(get_session),
    _auth: bool = Depends(verify_api_key),
    _rate: None = Depends(enforce_rate_limit),
):
    return await retry_failed_signals_core(session)


# ---------- Copy-trading feed (GET, per-subscriber key auth) ----------
class CopySignalItem(BaseModel):
    signal_id: str
    symbol: str
    direction: Literal["BUY", "SELL"]
    entry: float
    invalidation: float | None = None
    sl: float
    tp1: float
    tp2: float
    final_tp: float | None = None
    strategy: str | None = None
    confidence: int
    timeframe: str
    received_at: str


class CopyFeedResponse(BaseModel):
    copy_trading_enabled: bool
    signals: list[CopySignalItem]


@router.get("/copy/feed", response_model=CopyFeedResponse)
async def get_copy_feed(
    x_copy_key: str = Header(..., alias="X-Copy-Key"),
    session: AsyncSession = Depends(get_session),
):
    subscriber = await get_subscriber_by_copy_feed_key(session, x_copy_key)
    if subscriber is None:
        raise HTTPException(status_code=401, detail="Unrecognized copy-feed key")

    if not await can_copy(session, subscriber):
        raise HTTPException(status_code=403, detail="Copy trading is not currently active for this subscriber")

    result = await session.execute(
        select(Signal)
        .where(Signal.status == SignalStatus.ACTIVE, Signal.lifecycle_status == SignalLifecycleStatus.VALID)
        .order_by(Signal.received_at.desc())
        .limit(settings.COPY_FEED_MAX_SIGNALS)
    )
    signals = result.scalars().all()

    return CopyFeedResponse(
        copy_trading_enabled=True,
        signals=[
            CopySignalItem(
                signal_id=s.signal_id,
                symbol=s.symbol,
                direction=s.direction,
                entry=s.entry,
                invalidation=s.invalidation,
                sl=s.sl,
                tp1=s.tp1,
                tp2=s.tp2,
                final_tp=s.final_tp,
                strategy=s.strategy,
                confidence=s.confidence,
                timeframe=s.timeframe,
                received_at=s.received_at.isoformat() if s.received_at else "",
            )
            for s in signals
        ],
    )


# ---------- Subscription enforcement (admin cron trigger) ----------
@router.post("/admin/check-subscriptions")
async def check_subscriptions(_auth: bool = Depends(verify_api_key)):
    from app.database import async_session
    from app.group_enforcement import run_subscription_enforcement

    async with async_session() as session:
        result = await run_subscription_enforcement(session)
    return result