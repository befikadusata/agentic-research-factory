from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator # NEW
from database import init_db
from routers import runs, stream, hitl, upload, outputs, workspaces, analytics, verticals
from config import settings, validate_config
from utils.redis_client import init_redis_pool, close_redis_pool

import uuid
from logger import logger, request_id_var
from fastapi import Request

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
    return {"status": "ok"}
