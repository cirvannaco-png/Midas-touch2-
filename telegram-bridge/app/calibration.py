"""Scheduled recalibration work and the config-promotion lifecycle seam."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app import bot as bot_module
from app.bot_promotions import build_promotion_keyboard
from app.config import settings
from app.database import async_session
from app.logger import logger
from app.models import CalibrationCycle, PromotionRequest, SignalOutcome
from app.recalibration_lifecycle import evaluate_registered_challengers

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
for _candidate in (
    os.path.normpath(os.path.join(_APP_DIR, "..", "tools")),
    os.path.normpath(os.path.join(_APP_DIR, "..", "..", "tools")),
):
    if os.path.exists(os.path.join(_candidate, "metrics_engine.py")) and _candidate not in sys.path:
        sys.path.insert(0, _candidate)
        break
else:
    logger.warning(
        "app.calibration: couldn't locate tools/ (metrics_engine.py/gating.py) "
        "from either the deployed container layout or a repo checkout — "
        "POST /admin/run-cycle will fail until this is fixed."
    )

from environment_memory import as_report as build_environment_memory
from gating import GatingError, decide, load_cycles_from_db
from metrics_engine import compute_report
from regime_allocation import build_regime_allocations

CYCLE_WINDOW_WEEKS = 2
ENVIRONMENT_MEMORY_MIN_SAMPLE = 30


async def _fetch_window_rows(since: datetime) -> list:
    async with async_session() as session:
        result = await session.execute(select(SignalOutcome).where(SignalOutcome.received_at >= since))
        return list(result.scalars().all())


async def _latest_regime_allocations() -> dict[str, float]:
    async with async_session() as session:
        previous = await session.scalar(
            select(CalibrationCycle)
            .where(CalibrationCycle.source == "live")
            .order_by(CalibrationCycle.generated_at.desc())
            .limit(1)
        )
    if previous is None or not isinstance(previous.report_json, dict):
        return {}
    raw = previous.report_json.get("regime_allocations", {})
    if not isinstance(raw, dict):
        return {}
    allocations: dict[str, float] = {}
    for regime, evidence in raw.items():
        if not isinstance(evidence, dict):
            continue
        value = evidence.get("risk_multiplier")
        if isinstance(value, (int, float)):
            allocations[str(regime)] = float(value)
    return allocations


async def _persist_cycle(report: dict) -> CalibrationCycle:
    cycle_id = f"live_{report['generated_at'].replace(':', '').replace('+', '_')}"
    row = CalibrationCycle(
        cycle_id=cycle_id,
        source="live",
        generated_at=datetime.fromisoformat(report["generated_at"]),
        report_json=report,
    )
    async with async_session() as session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


def _format_summary(weight_version: str, decision, cycle_report: dict) -> str:
    lines = [
        f"📊 MEDIS TOUCH — Calibration cycle ({weight_version})",
        "",
        f"Decision: {decision.action}",
        f"Cycles considered: {decision.cycles_considered}",
        "",
    ]
    for line in decision.reasoning:
        lines.append(f"• {line}")
    lines.append("")
    for mv in decision.metric_verdicts:
        overlap_label = "no change" if mv.overlap else ("DIVERGED" if mv.overlap is False else "not estimable")
        lines.append(f"{mv.metric}: {overlap_label}")
        if mv.prior.is_estimable:
            lines.append(f"  prior:  {mv.prior.value:.3f} [{mv.prior.ci_low:.3f}, {mv.prior.ci_high:.3f}] (n={mv.prior.n})")
        if mv.latest.is_estimable:
            lines.append(f"  latest: {mv.latest.value:.3f} [{mv.latest.ci_low:.3f}, {mv.latest.ci_high:.3f}] (n={mv.latest.n})")

    cov = cycle_report.get("coverage", {})
    no_fill_rate = cov.get("no_fill_rate")
    no_fill_str = f"{no_fill_rate * 100:.1f}%" if no_fill_rate is not None else "n/a"
    lines += [
        "",
        f"Coverage this cycle: {cov.get('total_signals', 0)} signals, no-fill rate {no_fill_str}",
    ]

    memory = cycle_report.get("environment_strategy_memory", [])
    if memory:
        qualified = sum(1 for row in memory if row.get("status") == "QUALIFIED")
        degraded = sum(1 for row in memory if row.get("status") == "DEGRADED")
        lines += [
            "",
            f"Environment→strategy memory: {len(memory)} observed cells; {qualified} qualified, {degraded} degraded.",
            f"Minimum evidence threshold: {ENVIRONMENT_MEMORY_MIN_SAMPLE} resolved trades per cell.",
        ]

    allocations = cycle_report.get("regime_allocations", {})
    if allocations:
        lines.append("\nRegime risk allocations (statistically gated):")
        for regime, evidence in sorted(allocations.items()):
            multiplier = evidence.get("risk_multiplier")
            reason = evidence.get("reason", "")
            if multiplier is not None:
                lines.append(f"• {regime}: {float(multiplier):.2f}x — {reason}")
    return "\n".join(lines)


async def _send_config_promotion_cards(promotion_ids: list[int]) -> None:
    if not promotion_ids:
        return
    if bot_module.application is None or bot_module.application.bot is None:
        logger.warning("app.calibration: bot application not initialized — config promotion cards not sent")
        return

    for promotion_id in promotion_ids:
        async with async_session() as session:
            promo = await session.get(PromotionRequest, promotion_id)
            if promo is None or promo.status != "pending":
                continue
            text = (
                "🧪 MEDIS TOUCH — Challenger promotion\n\n"
                f"Instrument: {promo.instrument}\n"
                f"Timeframe: {promo.timeframe}\n"
                f"Configuration: {promo.config_hash}\n"
                f"Optimizer version: {promo.weight_version}\n\n"
                "Approval stages CHALLENGER → CHAMPION. It does NOT activate the EA. "
                "The EA must subsequently ACK this exact configuration hash."
            )
            try:
                msg = await bot_module.application.bot.send_message(
                    chat_id=settings.ADMIN_CHAT_ID,
                    text=text,
                    reply_markup=build_promotion_keyboard(promo.id),
                )
                promo.telegram_message_id = msg.message_id
                await session.commit()
            except Exception as e:
                logger.error(
                    f"app.calibration: failed to send config promotion card {promotion_id} "
                    f"({type(e).__name__}): {e}"
                )


async def run_cycle() -> dict:
    now = datetime.now(timezone.utc)
    since = now - timedelta(weeks=CYCLE_WINDOW_WEEKS)

    rows = await _fetch_window_rows(since)
    if not rows:
        logger.info("app.calibration.run_cycle: no signal_outcomes rows in the current window — nothing to do.")
        return {"status": "no_data", "since": since.isoformat()}

    report = compute_report(rows)
    report["environment_strategy_memory"] = build_environment_memory(
        rows,
        min_sample=ENVIRONMENT_MEMORY_MIN_SAMPLE,
    )

    previous_allocations = await _latest_regime_allocations()
    report["regime_allocations"] = build_regime_allocations(
        rows,
        previous=previous_allocations,
    )
    report["regime_allocation_policy"] = {
        "source": "resolved_signal_outcomes",
        "requires_statistical_qualification": True,
        "previous_allocations": previous_allocations,
    }

    cycle = await _persist_cycle(report)
    logger.info(
        f"app.calibration.run_cycle: persisted cycle {cycle.cycle_id} "
        f"({len(rows)} rows, {report['expectancy']['resolved_count']} resolved, "
        f"{len(report['environment_strategy_memory'])} environment-memory cells)."
    )

    weight_versions = list(report.get("expectancy", {}).get("by_weight_version_stats", {}).keys())
    decisions = []

    for wv in weight_versions:
        try:
            history = await load_cycles_from_db(weight_version=wv, source="live")
            decision = decide(history, wv)
        except GatingError as e:
            logger.warning(f"app.calibration.run_cycle: gating refused for {wv}: {e}")
            continue

        decisions.append({"weight_version": wv, "action": decision.action})

        if decision.action in ("HOLD", "INSUFFICIENT_DATA"):
            logger.info(f"app.calibration.run_cycle: {wv} -> {decision.action}, no message sent.")
            continue

        async with async_session() as session:
            promo = PromotionRequest(
                weight_version=wv,
                action=decision.action,
                decision_json=decision.to_dict(),
                status="pending" if decision.action == "PROMOTE" else "auto_executed",
                decided_at=None if decision.action == "PROMOTE" else now,
            )
            session.add(promo)
            await session.commit()
            await session.refresh(promo)

        summary = _format_summary(wv, decision, report)
        if decision.action == "ROLLBACK":
            summary += "\n\n⚠️ AUTO-ROLLBACK — contradiction is never silently reconciled; runtime config-sync still requires an exact EA ACK before any champion becomes active."

        try:
            if bot_module.application is None or bot_module.application.bot is None:
                logger.warning("app.calibration.run_cycle: bot application not initialized — summary not sent.")
            else:
                keyboard = build_promotion_keyboard(promo.id) if decision.action == "PROMOTE" else None
                msg = await bot_module.application.bot.send_message(
                    chat_id=settings.ADMIN_CHAT_ID, text=summary, reply_markup=keyboard,
                )
                async with async_session() as session:
                    db_promo = await session.get(PromotionRequest, promo.id)
                    db_promo.telegram_message_id = msg.message_id
                    await session.commit()
        except Exception as e:
            logger.error(
                f"app.calibration.run_cycle: failed to send promotion card for {wv} "
                f"({type(e).__name__}): {e}"
            )

    async with async_session() as session:
        config_lifecycle = await evaluate_registered_challengers(session)
    await _send_config_promotion_cards(config_lifecycle.get("promotion_ids", []))

    return {
        "status": "ok",
        "cycle_id": cycle.cycle_id,
        "resolved_count": report["expectancy"]["resolved_count"],
        "environment_strategy_memory_cells": len(report["environment_strategy_memory"]),
        "regime_allocations": report["regime_allocations"],
        "decisions": decisions,
        "config_lifecycle": config_lifecycle,
    }
