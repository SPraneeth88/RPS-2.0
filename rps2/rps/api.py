"""
FastAPI application — the natural-language interface plus supporting REST API.

Endpoints
  GET  /                 -> the operations console (static UI)
  POST /api/chat         -> conversational entry point (runs the LangGraph agent)
  GET  /api/vehicles     -> fleet list
  GET  /api/reservations -> reservation list
  POST /api/vehicles     -> onboard a vehicle (security aspect applies)
  GET  /api/summary      -> fleet counters for the dashboard header
  GET  /api/metrics      -> AOP observability snapshot (audit trail + latency)
  GET  /api/health       -> liveness + whether the LLM NLU is active
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from . import repository as repo
from .agent.graph import run_agent
from .aspects import observability_snapshot, require_admin_key
from .config import settings
from .database import init_db
from .schemas import ChatRequest, ChatResponse, VehicleCreate


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="RPS 2.0 — Agentic Reservation Processing System",
    version="2.0.0",
    lifespan=lifespan,
)

_STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    out = run_agent(req.message)
    return ChatResponse(**out)


@app.get("/api/vehicles")
def vehicles(vehicle_type: str | None = None) -> dict:
    return {"vehicles": repo.list_vehicles(vehicle_type)}


@app.get("/api/reservations")
def reservations(active_only: bool = False) -> dict:
    return {"reservations": repo.list_reservations(active_only)}


@app.post("/api/vehicles", dependencies=[Depends(require_admin_key)])
def add_vehicle(body: VehicleCreate) -> dict:
    try:
        v = repo.register_vehicle(
            body.make, body.model, body.vehicle_type,
            body.registration_number, body.daily_rate, body.location,
        )
        return {"vehicle": v}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/summary")
def summary() -> dict:
    return repo.fleet_summary()


@app.get("/api/metrics")
def metrics() -> dict:
    return observability_snapshot()


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "nlu": "llm" if settings.llm_enabled else "rules",
        "database": settings.database_url.split("://")[0],
    }


# Serve any other static assets (css/js) under /static.
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
