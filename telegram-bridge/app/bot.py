"""
Inbound bot wiring: builds the python-telegram-bot Application, registers
command handlers, and manages the Telegram webhook subscription.

This runs in *webhook* mode, not polling. Render exposes a single HTTP
port per web service - polling would mean a second long-running process
Render has no straightforward way to host alongside the FastAPI server on
a free/starter plan. Webhook mode fits the existing deployment exactly:
Telegram POSTs updates to POST /telegram/webhook (see routes.py), which
hands them to application.process_update(). No second process, no extra
Render service.

Mirrors the init_http_client()/close_http_client() pattern in telegram.py
so app/main.py's lifespan reads consistently.
"""

from __future__ import annotations

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from app.bot_handlers import (
    COMMAND_LIST,
    analysis,
    help_command,
    mute,
    muted_command,
    pause,
    performance,
    positions,
    resume,
    retry,
    risk,
    signal,
    start,
    stats,
    status,
    symbols_command,
    unknown_command,
    unmute,
    version_command,
)
from app.bot_promotions import CALLBACK_PREFIX, handle_promotion_callback
from app.config import settings
from app.copytrading_admin import (
    COPYTRADING_COMMAND_LIST,
    checkpayments_command,
    confirm_text_handler,
    copytrading_command,
)
from app.logger import logger
from app.payments_bot import (
    PAYMENTS_COMMAND_LIST,
    my_subscription,
    precheckout_callback,
    subscribe,
    successful_payment_callback,
)

application: Application | None = None

# Both new command groups append to bot_handlers.COMMAND_LIST *in place*
# (same list object, not a copy) — help_command() in bot_handlers.py reads
# that name at call time, so this keeps exactly one source of truth for
# /help and set_my_commands() below without bot_handlers.py needing to
# know these two modules exist.
for _name, _desc in PAYMENTS_COMMAND_LIST + COPYTRADING_COMMAND_LIST:
    if _name not in {n for n, _ in COMMAND_LIST}:
        COMMAND_LIST.append((_name, _desc))


def _build_application() -> Application:
    app = ApplicationBuilder().token(settings.BOT_TOKEN).updater(None).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("signal", signal))
    app.add_handler(CommandHandler("analysis", analysis))
    app.add_handler(CommandHandler("positions", positions))
    app.add_handler(CommandHandler("risk", risk))
    app.add_handler(CommandHandler("performance", performance))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("symbols", symbols_command))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))
    app.add_handler(CommandHandler("muted", muted_command))
    app.add_handler(CommandHandler("pause", pause))
    app.add_handler(CommandHandler("resume", resume))
    app.add_handler(CommandHandler("retry", retry))
    app.add_handler(CommandHandler("version", version_command))
    # v2.11 step 5 — tap-to-approve promotion cards. Pattern-matched on
    # the "promo:" prefix (see bot_promotions.py) so this handler can't
    # accidentally swallow callback_query updates from some future,
    # unrelated inline-keyboard feature.
    app.add_handler(CallbackQueryHandler(handle_promotion_callback, pattern=f"^{CALLBACK_PREFIX}:"))

    # --- Payments (app/payments_bot.py) ---
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("mysubscription", my_subscription))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # --- Copy-trading admin controls (app/copytrading_admin.py) ---
    app.add_handler(CommandHandler("copytrading", copytrading_command))
    app.add_handler(CommandHandler("checkpayments", checkpayments_command))
    # Plain-text (non-command) handler for the "yes" confirmation that
    # /copytrading on requires. filters.COMMAND is explicitly excluded so
    # this can never intercept an actual "/whatever" before the
    # catch-all below gets a chance to run - the two filter sets are
    # disjoint by construction, but the exclusion is kept explicit rather
    # than relying on that being obvious from registration order alone.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_text_handler))

    # Catches any other "/whatever" sent to the bot. Must be added last -
    # PTB tries handlers in registration order and stops at the first match,
    # so this only fires when none of the specific commands above matched.
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    return app


async def init_bot() -> None:
    """Build the Application, register commands with Telegram, and point
    the webhook at this service. Called once from main.py's lifespan.

    Everything below this point talks to Telegram's API over the network.
    Mirrors check_bot_token()'s style in telegram.py: any failure here (bad
    token, Telegram outage, no network reachability) is logged and
    swallowed rather than raised, so a Telegram-side problem degrades only
    the bot's inbound commands instead of crash-looping the whole service -
    outbound signal/trade alerts via POST /signal and /trade don't depend
    on any of this.
    """
    global application
    application = _build_application()

    try:
        await application.initialize()
        await application.start()

        await application.bot.set_my_commands(
            [BotCommand(name, desc) for name, desc in COMMAND_LIST]
        )

        if not settings.RENDER_EXTERNAL_URL and not settings.WEBHOOK_URL:
            logger.warning(
                "Neither RENDER_EXTERNAL_URL nor WEBHOOK_URL is set — "
                "skipping set_webhook(). Inbound commands (/start, "
                "/positions, ...) will not work until the webhook is "
                "registered."
            )
            return

        url = settings.webhook_url
        await application.bot.set_webhook(
            url=url,
            secret_token=settings.WEBHOOK_SECRET_TOKEN,
            # v2.11 — "callback_query" added for step 5's tap-to-approve
            # promotion cards (InlineKeyboardButton taps arrive as
            # callback_query updates, never as "message"). Without this,
            # Telegram silently never delivers button taps to this
            # webhook at all — process_update()/application.process_update()
            # are already update-type-agnostic (see bot.py), so this one
            # line was the actual gap.
            # "pre_checkout_query" added for Telegram Payments (see
            # app/payments_bot.py) — same category of gap: it's a distinct
            # update type, not a "message", and answerPreCheckoutQuery
            # must land within Telegram's 10-second window or the payment
            # is cancelled client-side, so this can't be missing silently.
            # successful_payment itself needs no new entry here — it
            # arrives as an ordinary "message" update, already allowed.
            allowed_updates=["message", "callback_query", "pre_checkout_query"],
            drop_pending_updates=True,
        )
        logger.info(f"Telegram webhook set to {url}")
    except Exception as e:
        logger.warning(
            f"Bot setup incomplete - inbound commands may not work "
            f"({type(e).__name__}): {e}"
        )


async def shutdown_bot() -> None:
    global application
    if application is None:
        return
    try:
        await application.stop()
        await application.shutdown()
    except Exception as e:
        # Mirrors init_bot(): if startup only partially completed (e.g.
        # initialize() succeeded but the network died before start()),
        # stop()/shutdown() can themselves raise. Never let bot teardown
        # block the rest of the app's shutdown sequence.
        logger.warning(f"Bot shutdown incomplete ({type(e).__name__}): {e}")
    finally:
        application = None


async def process_update(data: dict) -> None:
    if application is None:
        raise RuntimeError("Bot application not initialized - call init_bot() on startup")
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
