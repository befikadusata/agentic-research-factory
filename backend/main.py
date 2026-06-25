import asyncio
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator
from database import init_db
from routers import runs, stream, hitl, upload, outputs, workspaces, analytics, verticals
from config import settings, validate_config
from utils.redis_client import init_redis_pool, close_redis_pool
from logger import logger, request_id_var

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_config(settings)
    init_redis_pool()
    yield
    await close_redis_pool()

app = FastAPI(title="Agentic Research Factory", lifespan=lifespan)

# Instrumentator setup
Instrumentator().instrument(app).expose(app)

@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = request_id_var.set(rid)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        request_id_var.reset(token)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs.router,        prefix="/runs",        tags=["runs"])
app.include_router(stream.router,      prefix="/runs",        tags=["stream"])
app.include_router(hitl.router,        prefix="/runs",        tags=["hitl"])
app.include_router(upload.router,      prefix="/upload",      tags=["upload"])
app.include_router(outputs.router,     prefix="/runs",        tags=["outputs"])
app.include_router(workspaces.router,  prefix="/workspaces",  tags=["workspaces"])
app.include_router(analytics.router,   prefix="/analytics",   tags=["analytics"])
app.include_router(verticals.router,   tags=["verticals"])

@app.get("/health")
async def health():
    from fastapi.responses import JSONResponse
    from sqlalchemy import text
    from database import AsyncSessionLocal
    from utils.redis_client import get_redis_client

    checks = {}
    status_code = 200

    try:
        async with AsyncSessionLocal() as db:
            await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=2)
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "error"
        status_code = 503

    try:
        redis = await asyncio.wait_for(get_redis_client(), timeout=2)
        await asyncio.wait_for(redis.ping(), timeout=2)
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
        status_code = 503

    return JSONResponse({"status": "ok" if status_code == 200 else "degraded", **checks}, status_code=status_code)
