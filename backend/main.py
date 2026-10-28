import asyncio
import os
import urllib.request

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db, record_keepalive
from backend.routers import router

KEEP_ALIVE_URL = os.getenv("KEEP_ALIVE_URL") or os.getenv("RENDER_KEEPALIVE_URL")
KEEP_ALIVE_INTERVAL_SECONDS = int(os.getenv("KEEP_ALIVE_INTERVAL_SECONDS", "840"))

init_db()

app = FastAPI(
    title="AI-COS (AI Campus Operating System)",
    description="SQLite-backed campus operations APIs with a background keep-alive mechanism for hosted deployments.",
    version="3.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def keep_alive_loop() -> None:
    while True:
        await asyncio.sleep(KEEP_ALIVE_INTERVAL_SECONDS)
        if not KEEP_ALIVE_URL:
            continue
        try:
            with urllib.request.urlopen(KEEP_ALIVE_URL, timeout=10) as response:
                status = response.status
                record_keepalive(f"http_{status}")
        except Exception:
            record_keepalive("failed")


@app.on_event("startup")
async def startup_event() -> None:
    init_db()
    app.state.keepalive_task = asyncio.create_task(keep_alive_loop())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    task = getattr(app.state, "keepalive_task", None)
    if task is not None:
        task.cancel()


app.include_router(router)


@app.get("/")
def health_check() -> dict[str, str]:
    return {"system": "AI-COS Core", "status": "Online and Ready", "api_version": "v1"}


@app.get("/keep-alive")
def keep_alive() -> dict[str, str]:
    record_keepalive("manual")
    return {"status": "ok", "message": "keep-alive ping accepted", "service": "AI-COS Core"}
