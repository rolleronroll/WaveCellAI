# FastAPI application initialization root

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import get_settings
from ..deps import get_store
from .routes.sms import router as sms_router
# from .api.demo_relay import demo_relay
from . import demo_relay

settings = get_settings()

app = FastAPI(title="TravelAI Backend")
app.include_router(sms_router)

app.include_router(demo_relay.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    try:
        get_store()
        db_ok = True
    except FileNotFoundError:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "knowledge_db": db_ok,
        # booleans only, never the key values
        "keys": {
            "google": bool(settings.google_api_key),
            "anthropic": bool(settings.anthropic_api_key),
        },
    }