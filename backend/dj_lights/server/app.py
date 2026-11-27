"""FastAPI factory + engine lifecycle."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router as api_router
from .state import AppState
from .ws import router as ws_router


def _data_dir() -> Path:
    raw = os.environ.get("DJ_LIGHTS_DATA_DIR")
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[2] / "data"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    state = AppState.build(data_dir=_data_dir())
    app.state.dj_lights = state
    await state.wled_discovery.start()
    state.engine_task = asyncio.create_task(state.engine.run())
    try:
        yield
    finally:
        if state.wled_mirror is not None:
            await state.wled_mirror.stop()
        await state.wled_discovery.stop()
        state.engine.stop()
        if state.engine_task is not None:
            state.engine_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await state.engine_task


def create_app() -> FastAPI:
    app = FastAPI(title="DJ Lights POC", lifespan=_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    app.include_router(ws_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
