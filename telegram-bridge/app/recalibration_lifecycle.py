"""Database-backed recalibration lifecycle for immutable configurations."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.config_evaluation_model import ConfigurationEvaluation
from app.config_promotion_gate import evaluate_challenger
from app.config_registry_model import ConfigurationRegistry
from app.logger import logger
from app.models import PromotionRequest
from tools.recalibration_guard import PromotionPolicy


def _policy_from_settings() -> PromotionPolicy | None:
    values = (
        settings.RECALIBRATION_MIN_SCORE_DELTA,
        settings.RECALIBRATION_MAX_OOS_DEGRADATION,
        settings.RECALIBRATION_MAX_PARAMETER_DEGRADATION,
    )
    if any(value is None for value in values):
        return None
    return PromotionPolicy(
        minimum_score_delta=float(settings.RECALIBRATION_MIN_SCORE_DELTA),
        maximum_oos_degradation=float(settings.RECALIBRATION_MAX_OOS_DEGRADATION),
        maximum_parameter_degradation=float(settings.RECALIBRATION_MAX_PARAMETER_DEGRADATION),
        maximum_p_value=(
            None if settings.RECALIBRATION_MAX_P_VALUE is None else float(settings.RECALIBRATION_MAX_P_VALUE)
        ),
    )


async def evaluate_registered_challengers(session: AsyncSession) -> dict:
    """Evaluate CHALLENGER rows and create at most one pending promotion per hash."""
    policy = _policy_from_settings()
    if policy is None:
        logger.info("recalibration lifecycle: promotion policy is not configured; holding all candidates")
        return {"status": "policy_not_configured", "promotions": 0, "holds": 0, "promotion_ids": []}

    candidates = list(
        (
            await session.scalars(
                select(ConfigurationRegistry)
                .where(ConfigurationRegistry.lifecycle_status == "CHALLENGER")
                .order_by(ConfigurationRegistry.created_at.asc())
            )
        ).all()
    )

    promotions = 0
    holds = 0
    promotion_ids: list[int] = []
    for challenger in candidates:
        champion = await session.scalar(
            select(ConfigurationRegistry)
            .where(
                ConfigurationRegistry.instrument == challenger.instrument,
                ConfigurationRegistry.strategy == challenger.strategy,
                ConfigurationRegistry.timeframe == challenger.timeframe,
                ConfigurationRegistry.lifecycle_status == "CHAMPION",
                ConfigurationRegistry.config_hash != challenger.config_hash,
            )
            .order_by(ConfigurationRegistry.created_at.desc())
            .limit(1)
        )
        if champion is None:
            holds += 1
            continue

        challenger_eval = await session.scalar(
            select(ConfigurationEvaluation)
            .where(ConfigurationEvaluation.config_hash == challenger.config_hash)
            .order_by(ConfigurationEvaluation.evidence_version.desc())
            .limit(1)
        )
        champion_eval = await session.scalar(
            select(ConfigurationEvaluation)
            .where(ConfigurationEvaluation.config_hash == champion.config_hash)
            .order_by(ConfigurationEvaluation.evidence_version.desc())
            .limit(1)
        )
        if challenger_eval is None or champion_eval is None:
            holds += 1
            continue

        decision = evaluate_challenger(champion_eval, challenger_eval, policy=policy)
        if decision.action != "PROMOTE":
            holds += 1
            continue

        existing = await session.scalar(
            select(PromotionRequest).where(
                and_(
                    PromotionRequest.config_hash == challenger.config_hash,
                    PromotionRequest.status.in_(["pending", "approved"]),
                )
            )
        )
        if existing is not None:
            continue

        promo = PromotionRequest(
            weight_version=challenger.optimizer_version,
            action="PROMOTE",
            decision_json={
                "action": decision.action,
                "reasons": list(decision.reasons),
                "config_hash": challenger.config_hash,
                "champion_hash": champion.config_hash,
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
            },
            config_hash=challenger.config_hash,
            instrument=challenger.instrument,
            timeframe=challenger.timeframe,
            status="pending",
        )
        session.add(promo)
        await session.flush()
        promotion_ids.append(promo.id)
        promotions += 1

    await session.commit()
    return {
        "status": "ok",
        "candidates": len(candidates),
        "promotions": promotions,
        "holds": holds,
        "promotion_ids": promotion_ids,
    }
