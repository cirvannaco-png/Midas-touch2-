"""Telegram tap-to-approve gate for recalibration promotions."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.config import settings
from app.config_registry_model import ConfigurationRegistry
from app.config_sync_state_model import ConfigSyncState
from app.database import async_session
from app.logger import logger
from app.models import ApprovedWeightVersion, PromotionRequest

CALLBACK_PREFIX = "promo"


def build_promotion_keyboard(promotion_request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"{CALLBACK_PREFIX}:approve:{promotion_request_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"{CALLBACK_PREFIX}:reject:{promotion_request_id}"),
    ]])


async def handle_promotion_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user

    if user is None or str(user.id) != settings.authorized_user_id:
        logger.warning(f"Ignored promotion callback from unauthorized user_id={user.id if user else None}")
        await query.answer("Not authorized.", show_alert=True)
        return

    try:
        _, action, id_str = query.data.split(":", 2)
        promotion_request_id = int(id_str)
    except (ValueError, AttributeError):
        await query.answer("Malformed callback data.", show_alert=True)
        return

    async with async_session() as session:
        promo = await session.get(PromotionRequest, promotion_request_id)
        if promo is None:
            await query.answer("This promotion request no longer exists.", show_alert=True)
            return

        if promo.status != "pending":
            await query.answer(f"Already {promo.status} — no action taken.", show_alert=True)
            return

        now = datetime.now(timezone.utc)
        promo.decided_at = now
        promo.decided_by = str(user.id)

        if action == "approve":
            if promo.config_hash:
                registry = await session.scalar(
                    select(ConfigurationRegistry).where(
                        ConfigurationRegistry.config_hash == promo.config_hash,
                        ConfigurationRegistry.instrument == promo.instrument,
                    )
                )
                if registry is None:
                    promo.status = "rejected"
                    await session.commit()
                    await query.answer("Candidate configuration is missing.", show_alert=True)
                    return
                if registry.lifecycle_status != "CHALLENGER":
                    promo.status = "rejected"
                    await session.commit()
                    await query.answer(
                        f"Candidate is {registry.lifecycle_status}; only CHALLENGER can become CHAMPION.",
                        show_alert=True,
                    )
                    return

                state = await session.scalar(
                    select(ConfigSyncState).where(ConfigSyncState.symbol == promo.instrument)
                )
                if state is None:
                    state = ConfigSyncState(symbol=promo.instrument, state="HOLD")
                    session.add(state)
                    await session.flush()

                # The human approval advances lifecycle state only. It does
                # NOT set active_config_hash. The EA must poll the exact
                # champion and ACK that exact hash before activation.
                registry.transition_to("CHAMPION")
                state.pending_activation_hash = registry.config_hash
                state.rollback_config_hash = state.active_config_hash
                state.state = "PENDING_ACK"
                state.last_error = None
                promo.status = "approved"
            else:
                # Legacy weight-only approvals remain an audit record. They
                # are intentionally unable to activate a concrete config.
                promo.status = "approved"

            existing = await session.scalar(
                select(ApprovedWeightVersion).where(ApprovedWeightVersion.weight_version == promo.weight_version)
            )
            if existing is None:
                session.add(ApprovedWeightVersion(
                    weight_version=promo.weight_version,
                    approved_by=str(user.id),
                    promotion_request_id=promo.id,
                ))
            verdict_line = f"✅ Approved by {user.first_name or user.id} at {now.strftime('%Y-%m-%d %H:%M UTC')}"
            if promo.config_hash:
                verdict_line += "\n⏳ Champion staged; waiting for exact EA ACK before activation."
        elif action == "reject":
            promo.status = "rejected"
            verdict_line = f"❌ Rejected by {user.first_name or user.id} at {now.strftime('%Y-%m-%d %H:%M UTC')}"
        else:
            await query.answer("Unknown action.", show_alert=True)
            return

        await session.commit()

    await query.answer("Recorded.")
    original_text = query.message.text or ""
    try:
        await query.edit_message_text(f"{original_text}\n\n{verdict_line}")
    except Exception as e:
        logger.warning(f"Couldn't edit promotion card after decision ({type(e).__name__}): {e}")

    logger.info(f"Promotion request {promotion_request_id} ({promo.weight_version}): {promo.status} by user_id={user.id}")
