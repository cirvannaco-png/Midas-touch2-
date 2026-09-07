"""
Admin-only Telegram controls for the copy-trading switch and the
subscription-enforcement sweep.

Same authorization boundary as every command in bot_handlers.py
(_authorized_only — settings.authorized_user_id only) — imported from
there rather than reimplemented, so there is exactly one definition of
"who's allowed to touch this bot's controls".

/copytrading on requires a second, explicit confirmation: the literal
text "yes", from the same admin, within COPY_TRADING_CONFIRM_TTL_SECONDS
— see app/settings_store.py:request_copy_trading_on /
confirm_copy_trading_on. /copytrading off has no such gate; see
settings_store.set_copy_trading_enabled's docstring for why the safe
direction shouldn't have friction added to it.
"""

from __future__ import annotations

from sqlalchemy import func, select
from telegram import Update
from telegram.ext import ContextTypes

from app.bot_handlers import _authorized_only
from app.config import settings
from app.database import async_session
from app.models import SUBSCRIBER_STATUS_ACTIVE, Subscriber
from app.settings_store import (
    confirm_copy_trading_on,
    get_pending_copy_trading_on,
    is_copy_trading_enabled,
    request_copy_trading_on,
    set_copy_trading_enabled,
)

COPYTRADING_COMMAND_LIST = [
    ("copytrading", "Copy-trading switch: /copytrading on|off|status"),
    ("checkpayments", "Run the subscription sweep now (warn/expire/remove)"),
]


@_authorized_only
async def copytrading_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = getattr(context, "args", None) or []
    action = args[0].lower() if args else "status"
    user_id = str(update.effective_user.id)

    async with async_session() as session:
        if action == "status":
            enabled = await is_copy_trading_enabled(session)
            pending = await get_pending_copy_trading_on(session)
            lines = [f"Copy trading: {'🟢 ON' if enabled else '🔴 OFF'}"]
            if pending is not None:
                lines.append('A pending ON request is awaiting "yes" confirmation.')
            await update.message.reply_text("\n".join(lines))
            return

        if action == "off":
            await set_copy_trading_enabled(session, False)
            await update.message.reply_text(
                "🔴 Copy trading turned OFF. GET /copy/feed now refuses every subscriber, "
                "immediately — no confirmation needed to reach this state."
            )
            return

        if action == "on":
            if await is_copy_trading_enabled(session):
                await update.message.reply_text("Copy trading is already ON.")
                return
            await request_copy_trading_on(session, user_id, settings.COPY_TRADING_CONFIRM_TTL_SECONDS)
            await update.message.reply_text(
                "⚠️ This activates real copy-trading dispatch — paying subscribers' copier "
                "scripts will start being able to pull live signals from GET /copy/feed.\n\n"
                f'Reply with exactly "yes" within {settings.COPY_TRADING_CONFIRM_TTL_SECONDS} '
                "seconds to confirm, or send anything else / do nothing to cancel."
            )
            return

        await update.message.reply_text("Usage: /copytrading on|off|status")


async def confirm_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Registered as a plain-text (non-command) MessageHandler in app/bot.py.
    Cheap on every other message: bails out before touching the database
    unless (a) the sender is the authorized admin and (b) the message is
    exactly "yes" (case-insensitive, whitespace-trimmed) — anyone else's
    chatter, or the admin's own unrelated messages, fall through with a
    single string comparison and no DB round-trip.
    """
    user = update.effective_user
    message = update.message
    if user is None or message is None or message.text is None:
        return
    if str(user.id) != settings.authorized_user_id:
        return
    if message.text.strip().lower() != "yes":
        return

    async with async_session() as session:
        confirmed = await confirm_copy_trading_on(session, str(user.id))

    if confirmed:
        await message.reply_text(
            "🟢 Copy trading turned ON. GET /copy/feed now serves entitled subscribers."
        )
    # If there was no pending request (or it expired, or this "yes" isn't
    # tied to one), this silently no-ops — an admin typing the word "yes"
    # in casual conversation with no pending request must not produce a
    # confusing bot reply about a control it never asked about.


@_authorized_only
async def checkpayments_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Manual trigger for the same sweep POST /admin/check-subscriptions
    runs — see app/group_enforcement.py. Useful for testing the pipeline
    or acting immediately instead of waiting for the next cron tick.
    """
    from app.group_enforcement import run_subscription_enforcement

    await update.message.reply_text("🔁 Running subscription sweep…")
    async with async_session() as session:
        active_count = await session.scalar(
            select(func.count()).select_from(Subscriber).where(Subscriber.status == SUBSCRIBER_STATUS_ACTIVE)
        )
        result = await run_subscription_enforcement(session)

    lines = [
        f"Active subscribers: {active_count}",
        f"Warned (expiring soon): {result['warned']}",
        f"Newly expired (in grace period): {result['expired']}",
        f"Removed from group (grace period over): {result['removed']}",
    ]
    await update.message.reply_text("\n".join(lines))
