"""
Telegram-native payment handlers.

This is Telegram Payments (Bot API `sendInvoice` / `answerPreCheckoutQuery`
/ `successful_payment`), not a third-party payment gateway with its own
webhook route and signature scheme. With SUBSCRIPTION_PROVIDER_TOKEN left
empty (the default — see app/config.py), Telegram settles in Stars (XTR)
and there's no external merchant account to configure at all: a person
taps Pay inside Telegram, Telegram tells the bot it succeeded via an
ordinary `successful_payment` message update, delivered through the same
POST /telegram/webhook -> process_update() path every other inbound
command already uses. See app/models.py:Payment for why this is a
meaningfully different (and simpler, more reliable) shape than a
provider webhook.

Nothing in this module talks to app.copy_trading or app.settings_store's
copy-trading flag — paying activates *entitlement*
(app/subscriptions.py:record_payment), which is necessary but not
sufficient for GET /copy/feed to actually return anything (see
app/copy_trading.py:can_copy — the global switch is separate, and is
never touched by a payment).
"""

from __future__ import annotations

from telegram import LabeledPrice, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from app.config import settings
from app.database import async_session
from app.logger import logger
from app.subscriptions import get_or_create_subscriber, record_payment

PAYMENTS_COMMAND_LIST = [
    ("subscribe", "Subscribe / renew (opens a Telegram payment)"),
    ("mysubscription", "Your subscription status and copy-feed key"),
]

_INVOICE_PAYLOAD_PREFIX = "medistouch_sub"


def _build_invoice_payload(telegram_user_id: int) -> str:
    # No secret/nonce needed here beyond the user id itself: this payload
    # is generated fresh per /subscribe call and only ever compared
    # against the *paying* user's own id in the pre-checkout handler
    # below (an attacker who somehow replayed someone else's payload
    # would just be paying to extend that other person's subscription,
    # not their own — not a privilege they gain anything from).
    return f"{_INVOICE_PAYLOAD_PREFIX}:{telegram_user_id}"


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /subscribe — open to any Telegram user, not admin-gated (unlike
    every handler in bot_handlers.py): this is how members actually pay,
    so it can't be restricted to settings.authorized_user_id.
    """
    user = update.effective_user
    if user is None or update.message is None:
        return

    async with async_session() as session:
        await get_or_create_subscriber(session, str(user.id), user.username)

    title = "Medis Touch — copy-trading access"
    description = (
        f"{settings.SUBSCRIPTION_PERIOD_DAYS}-day access to the Medis Touch copy-trading feed. "
        "Renews stack on top of remaining time if you pay early."
    )
    prices = [LabeledPrice("Medis Touch subscription", settings.SUBSCRIPTION_PRICE_AMOUNT)]

    try:
        await context.bot.send_invoice(
            chat_id=update.effective_chat.id,
            title=title,
            description=description,
            payload=_build_invoice_payload(user.id),
            provider_token=settings.SUBSCRIPTION_PROVIDER_TOKEN,
            currency=settings.SUBSCRIPTION_CURRENCY,
            prices=prices,
        )
    except TelegramError as e:
        logger.error(f"send_invoice failed for user_id={user.id} ({type(e).__name__}): {e}")
        await update.message.reply_text(
            "Couldn't open the payment window right now — please try /subscribe again shortly."
        )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Telegram requires an answer within 10 seconds or the payment is
    cancelled client-side. Only real validation possible/needed at this
    stage: the payload is ours and belongs to the user who's paying.
    Anything else (does this user already have an active period, etc.)
    is not a reason to refuse a payment — a renewal or an accidental
    double-payment is handled by record_payment()'s stacking logic
    after the fact, not by blocking checkout.
    """
    query = update.pre_checkout_query
    if query is None:
        return

    expected_prefix = f"{_INVOICE_PAYLOAD_PREFIX}:{query.from_user.id}"
    if query.invoice_payload != expected_prefix:
        await query.answer(ok=False, error_message="This payment link doesn't match your account. Send /subscribe again.")
        return

    await query.answer(ok=True)


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message is None or message.successful_payment is None or update.effective_user is None:
        return

    sp = message.successful_payment
    user = update.effective_user

    async with async_session() as session:
        subscriber = await get_or_create_subscriber(session, str(user.id), user.username)
        payment = await record_payment(
            session,
            subscriber,
            telegram_payment_charge_id=sp.telegram_payment_charge_id,
            amount=sp.total_amount,
            currency=sp.currency,
            invoice_payload=sp.invoice_payload,
            raw_payload=sp.to_dict(),
        )
        was_removed = subscriber.status == "removed"  # snapshot before record_payment overwrote it — see below
        period_end = subscriber.current_period_end

    if payment is None:
        # Duplicate delivery of an already-recorded charge — Telegram
        # redelivers webhook updates that weren't ack'd fast enough.
        # The subscriber's entitlement was already extended the first
        # time; don't message them twice about the same payment.
        return

    lines = [
        "✅ Payment received — thank you!",
        f"Your access is now active until {period_end.strftime('%Y-%m-%d %H:%M UTC')}.",
        "Send /mysubscription any time to check your status or copy-feed key.",
    ]
    await message.reply_text("\n".join(lines))

    if was_removed and settings.GROUP_CHAT_ID:
        await _welcome_back(context, user.id)


async def _welcome_back(context: ContextTypes.DEFAULT_TYPE, telegram_user_id: int) -> None:
    """
    Lifts the group_enforcement.py kick-ban (Telegram's kick pattern is
    ban then unban — see that module) and sends a fresh invite link.
    Bots cannot add an arbitrary user back into a group themselves
    (Telegram has no API for that, by design); an invite link is the
    correct mechanism. Best-effort: a failure here must not undo the
    payment or the entitlement that was already committed above.
    """
    try:
        await context.bot.unban_chat_member(
            chat_id=settings.GROUP_CHAT_ID, user_id=telegram_user_id, only_if_banned=True
        )
        invite = await context.bot.create_chat_invite_link(
            chat_id=settings.GROUP_CHAT_ID, member_limit=1, name=f"resub-{telegram_user_id}"
        )
        await context.bot.send_message(
            chat_id=telegram_user_id,
            text=f"Welcome back — here's your invite link back into the group: {invite.invite_link}",
        )
    except TelegramError as e:
        logger.warning(f"Could not restore group access for user_id={telegram_user_id} ({type(e).__name__}): {e}")


async def my_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Deliberately only replies in a private chat: copy_feed_api_key is a
    bearer credential (see app/models.py:Subscriber), and this command
    would otherwise happily paste it into the group chat if someone ran
    it there.
    """
    user = update.effective_user
    chat = update.effective_chat
    if user is None or update.message is None:
        return
    if chat is not None and chat.type != "private":
        await update.message.reply_text("Send /mysubscription in a DM with the bot — it includes a private key.")
        return

    async with async_session() as session:
        subscriber = await get_or_create_subscriber(session, str(user.id), user.username)

    if subscriber.current_period_end is None:
        await update.message.reply_text(
            "You don't have an active subscription yet. Send /subscribe to get started."
        )
        return

    lines = [
        f"Status: {subscriber.status}",
        f"Access until: {subscriber.current_period_end.strftime('%Y-%m-%d %H:%M UTC')}",
    ]
    if subscriber.copy_feed_api_key:
        lines.append(f"Copy-feed key: {subscriber.copy_feed_api_key}")
        lines.append("Keep this private — anyone with it can pull the copy-trading feed under your account.")
    await update.message.reply_text("\n".join(lines))
