"""Main FastAPI application entry point for Q-SAT Adaptive Ground Station.

An Intelligent Hardware-in-the-Loop Digital Twin and Adaptive AI Framework
for Satellite-to-Ground Quantum Communication.
"""

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
import asyncio
from backend.app.api.routes_system import router as system_router
from backend.app.api.routes_environment import router as environment_router
from backend.app.api.routes_simulation import router as simulation_router
from backend.app.api.routes_satellite import router as satellite_router
from backend.app.api.routes_qkd import router as qkd_router
from backend.app.api.routes_control import router as control_router
from backend.app.api.routes_ai import router as ai_router
from backend.app.api.routes_alerts import router as alerts_router
from backend.app.api.routes_experiments import router as experiments_router
from backend.app.websocket.manager import ws_manager
from fastapi import WebSocket, WebSocketDisconnect

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("qsat.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan lifecycle manager."""
    logger.info("Starting %s v%s in [%s] mode", settings.SYSTEM_NAME, settings.VERSION, settings.ENVIRONMENT_MODE)
    logger.info("Ground Station: Lat=%.4f, Lon=%.4f, Alt=%.1fm",
                settings.GROUND_STATION_LAT, settings.GROUND_STATION_LON, settings.GROUND_STATION_ALT)
    
    # Start live telemetry broadcast background task
    broadcast_task = asyncio.create_task(ws_manager.broadcast_telemetry())
    yield
    # Graceful shutdown
    broadcast_task.cancel()
    logger.info("Shutting down %s", settings.SYSTEM_NAME)


app = FastAPI(
    title=settings.SYSTEM_NAME,
    description=(
        "Q-SAT Adaptive Ground Station API: An Intelligent Hardware-in-the-Loop "
        "Digital Twin and Adaptive AI Framework for Satellite-to-Ground Quantum Communication."
    ),
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Enable CORS for frontend dashboard (Angular on default port 4200)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(system_router)
app.include_router(environment_router)
app.include_router(simulation_router)
app.include_router(satellite_router)
app.include_router(qkd_router)
app.include_router(control_router)
app.include_router(ai_router)
app.include_router(alerts_router)
app.include_router(experiments_router)


@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    """Real-time mission control WebSocket telemetry streaming endpoint."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and accept incoming client pings or control requests
            _client_msg = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


from fastapi.staticfiles import StaticFiles
import os

frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "qsat-dashboard", "dist", "qsat-dashboard", "browser")
if os.path.exists(frontend_dist):
    app.mount("/dashboard", StaticFiles(directory=frontend_dist, html=True), name="dashboard")

results_dist = os.path.join(os.path.dirname(__file__), "..", "..", "results")
if os.path.exists(results_dist):
    app.mount("/results-static", StaticFiles(directory=results_dist), name="results-static")


from fastapi import Request
from fastapi.responses import RedirectResponse, JSONResponse

@app.get("/", tags=["Root"])
async def root(request: Request):
    """Serve welcome JSON for API clients or redirect to interactive dashboard for browsers."""
    accept = request.headers.get("accept", "")
    if "text/html" in accept and os.path.exists(frontend_dist):
        return RedirectResponse(url="/dashboard/")
    return {
        "message": f"Welcome to {settings.SYSTEM_NAME}",
        "version": settings.VERSION,
        "docs": "/docs",
    }



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )
