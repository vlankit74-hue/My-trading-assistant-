"""
WebSocket hub for live prices.

Design: a single background task per symbol (started by the scheduler/
lifespan, see main.py) reads from the provider's stream and publishes to a
Redis channel. Each connected browser client subscribes to that channel
via this endpoint. This means N browser tabs share ONE upstream connection
to Twelve Data/Binance — critical for not blowing through premium API limits.
"""
import asyncio
import json

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.models.schemas import AssetSymbol
from app.services.cache_service import CacheService

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.websocket("/ws/prices/{symbol}")
async def ws_prices(websocket: WebSocket, symbol: AssetSymbol):
    await websocket.accept()
    settings = get_settings()
    cache = CacheService(settings)
    pubsub = cache.pubsub()
    channel = f"prices:{symbol.value}"
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        logger.info("ws_client_disconnected", symbol=symbol.value)
    except asyncio.CancelledError:
        raise
    finally:
        await pubsub.unsubscribe(channel)
        await cache.close()
