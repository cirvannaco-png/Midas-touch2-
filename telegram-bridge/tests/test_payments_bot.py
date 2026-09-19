"""Tests for app.payments_bot using direct async handler invocation."""
from unittest.mock import AsyncMock

import pytest

from app.database import async_session
from app.payments_bot import my_subscription, precheckout_callback, subscribe, successful_payment_callback
from app.subscriptions import get_subscriber_by_user_id, is_entitled


class _FakeMessage:
    def __init__(self, successful_payment=None):
        self.successful_payment = successful_payment
        self.replies: list[str] = []

    async def reply_text(self, text):
        self.replies.append(text)


class _FakeChat:
    def __init__(self, chat_id, chat_type="private"):
        self.id = chat_id
        self.type = chat_type


class _FakeUser:
    def __init__(self, user_id, username="tester"):
        self.id = user_id
        self.username = username


class _FakeUpdate:
    def __init__(self, user_id=5001, chat_type="private", successful_payment=None):
        self.effective_user = _FakeUser(user_id)
        self.effective_chat = _FakeChat(user_id, chat_type)
        self.message = _FakeMessage(successful_payment)


class _FakePreCheckoutQuery:
    def __init__(self, user_id, invoice_payload):
        self.from_user = _FakeUser(user_id)
        self.invoice_payload = invoice_payload
        self.answers: list[dict] = []

    async def answer(self, ok, error_message=None):
        self.answers.append({"ok": ok, "error_message": error_message})


class _FakePreCheckoutUpdate:
    def __init__(self, query):
        self.pre_checkout_query = query


class _FakeSuccessfulPayment:
    def __init__(self, charge_id, amount, currency, invoice_payload):
        self.telegram_payment_charge_id = charge_id
        self.total_amount = amount
        self.currency = currency
        self.invoice_payload = invoice_payload

    def to_dict(self):
        return {
            "telegram_payment_charge_id": self.telegram_payment_charge_id,
            "total_amount": self.total_amount,
            "currency": self.currency,
            "invoice_payload": self.invoice_payload,
        }


class _FakeBot:
    def __init__(self):
        self.sent_invoices: list[dict] = []

    async def send_invoice(self, **kwargs):
        self.sent_invoices.append(kwargs)


class _FakeContext:
    def __init__(self):
        self.bot = _FakeBot()


@pytest.mark.asyncio
async def test_subscribe_sends_invoice_and_creates_subscriber():
    update = _FakeUpdate(user_id=5001)
    context = _FakeContext()

    await subscribe(update, context)

    assert len(context.bot.sent_invoices) == 1
    assert context.bot.sent_invoices[0]["payload"] == "medistouch_sub:5001"

    async with async_session() as session:
        sub = await get_subscriber_by_user_id(session, "5001")
        assert sub is not None


@pytest.mark.asyncio
async def test_precheckout_accepts_matching_payload():
    query = _FakePreCheckoutQuery(5002, "medistouch_sub:5002")
    await precheckout_callback(_FakePreCheckoutUpdate(query), None)
    assert query.answers == [{"ok": True, "error_message": None}]


@pytest.mark.asyncio
async def test_precheckout_rejects_mismatched_payload():
    query = _FakePreCheckoutQuery(5003, "medistouch_sub:someone-else")
    await precheckout_callback(_FakePreCheckoutUpdate(query), None)
    assert query.answers[0]["ok"] is False


@pytest.mark.asyncio
async def test_successful_payment_activates_entitlement_and_replies():
    payment = _FakeSuccessfulPayment("charge-abc", 500, "XTR", "medistouch_sub:5004")
    update = _FakeUpdate(user_id=5004, successful_payment=payment)

    await successful_payment_callback(update, None)

    assert update.message.replies
    assert "Payment received" in update.message.replies[0]

    async with async_session() as session:
        sub = await get_subscriber_by_user_id(session, "5004")
        assert is_entitled(sub) is True


@pytest.mark.asyncio
async def test_duplicate_successful_payment_does_not_reply_twice():
    payment = _FakeSuccessfulPayment("charge-dup", 500, "XTR", "medistouch_sub:5005")

    update1 = _FakeUpdate(user_id=5005, successful_payment=payment)
    await successful_payment_callback(update1, None)
    assert len(update1.message.replies) == 1

    update2 = _FakeUpdate(user_id=5005, successful_payment=payment)
    await successful_payment_callback(update2, None)
    assert len(update2.message.replies) == 0


@pytest.mark.asyncio
async def test_mysubscription_refuses_in_group_chat():
    update = _FakeUpdate(user_id=5006, chat_type="group")
    await my_subscription(update, None)
    assert update.message.replies
    assert "DM" in update.message.replies[0]


@pytest.mark.asyncio
async def test_mysubscription_shows_status_in_private_chat():
    payment = _FakeSuccessfulPayment("charge-mysub", 500, "XTR", "medistouch_sub:5007")
    await successful_payment_callback(_FakeUpdate(user_id=5007, successful_payment=payment), None)

    update = _FakeUpdate(user_id=5007, chat_type="private")
    await my_subscription(update, None)
    assert update.message.replies
    reply = update.message.replies[0]
    assert "active" in reply.lower()
    assert "Copy-feed key" in reply
