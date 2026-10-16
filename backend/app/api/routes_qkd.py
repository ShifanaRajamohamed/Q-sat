"""Quantum Key Distribution (QKD) analytical API routes."""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from backend.app.models.qkd import QKDMetrics
from backend.app.services.qkd_service import qkd_service

router = APIRouter(prefix="/api/qkd", tags=["QKD"])


class AnomalyRequest(BaseModel):
    qber_offset: float = Field(0.08, ge=0.0, le=0.40, description="QBER offset to inject (e.g. 0.08 = +8% error)")


@router.get("/current", response_model=QKDMetrics, summary="Get current QKD communication performance metrics")
async def get_current_qkd() -> QKDMetrics:
    """Return latest QKD state: QBER, raw rate, sifted rate, asymptotic SKR, channel loss, and root-cause breakdown."""
    return qkd_service.get_metrics()


@router.post("/anomaly", summary="Inject simulated security anomaly component")
async def inject_anomaly(payload: AnomalyRequest):
    """Simulate eavesdropping attack or quantum channel physical fault by injecting QBER."""
    qkd_service.inject_anomaly(payload.qber_offset)
    return {"status": "success", "injected_qber_offset": payload.qber_offset}


@router.delete("/anomaly", summary="Clear active security anomaly injection")
async def clear_anomaly():
    """Reset security anomaly injection back to 0.0."""
    qkd_service.clear_anomaly()
    return {"status": "success", "message": "Anomaly injection cleared"}
