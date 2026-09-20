import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, Response

from app.api.config_sync import router as config_sync_router
from app.api.environment_outcomes import router as environment_outcome_router
from app.bot import init_bot, shutdown_bot
from app.config import APP_VERSION, settings
from app.logger import logger
from app.routes import router
from app.signal_outbox import run_outbox_worker
from app.telegram import close_http_client, init_http_client


class RequestBodyTooLarge(Exception):
    pass


class MaxBodySizeMiddleware:
    """
    Raw ASGI middleware. Rejects on Content-Length first (cheap, catches the
    common case), and also enforces the limit against the actual bytes streamed
    in - a Content-Length header is caller-supplied and can be absent (chunked
    transfer) or simply wrong, so it can't be trusted alone.
    """

    def __init__(self, app, max_size: int):
        self.app = app
        self.max_size = max_size

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        for key, value in scope.get("headers", []):
            if key == b"content-length":
                try:
                    if int(value) > self.max_size:
                        response = Response(
                            content='{"detail":"Request body too large"}',
                            status_code=413,
                            media_type="application/json",
                        )
                        await response(scope, receive, send)
                        return
                except ValueError:
                    pass
                break

        total = 0

        async def limited_receive():
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > self.max_size:
                    raise RequestBodyTooLarge()
            return message

        await self.app(scope, limited_receive, send)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting application...")
        await init_http_client()
        outbox_stop = asyncio.Event()
        outbox_task = None
        # init_bot() already performs Telegram API initialization and
        # handles Telegram-side failures. Avoid a redundant getMe request
        # on every cold start.
        await init_bot()
        outbox_task = asyncio.create_task(run_outbox_worker(outbox_stop))
        yield
        outbox_stop.set()
        if outbox_task is not None:
            outbox_task.cancel()
            try:
                await outbox_task
            except asyncio.CancelledError:
                pass
        await shutdown_bot()
        await close_http_client()
        logger.info("Shutdown complete.")

    app = FastAPI(title="Medis Touch Telegram Bridge", version=APP_VERSION, lifespan=lifespan)

    allowed_origins = settings.allowed_origins_list
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["POST", "GET"],
            allow_headers=["X-API-Key", "Content-Type"],
        )

    app.add_middleware(MaxBodySizeMiddleware, max_size=settings.MAX_REQUEST_BODY_SIZE)

    @app.exception_handler(RequestBodyTooLarge)
    async def body_too_large_handler(request, exc):
        return JSONResponse(status_code=413, content={"detail": "Request body too large"})

    # Mount the immutable config-sync protocol first. The rich environment
    # outcome boundary is also mounted before the legacy /outcome route so
    # upgraded EA payloads are persisted without breaking older clients.
    app.include_router(config_sync_router)
    app.include_router(environment_outcome_router)
    app.include_router(router)

    return app


app = create_app()