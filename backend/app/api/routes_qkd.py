"""Quantum Key Distribution (QKD) analytical API routes."""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from backend.app.models.qkd import QKDMetrics
from backend.app.services.qkd_service import qkd_service

router = APIRouter(prefix="/api/qkd", tags=["QKD"])


from typing import Optional

class AnomalyRequest(BaseModel):
    qber_offset: Optional[float] = Field(None, ge=0.0, le=0.40, description="QBER offset to inject (e.g. 0.08 = +8% error)")
    magnitude: Optional[float] = Field(None, ge=0.0, le=0.40, description="Alternative key for QBER offset")
    anomaly_type: Optional[str] = Field("EAVESDROPPING", description="Classification tag for simulated anomaly")
    duration_steps: Optional[int] = Field(30, description="Duration in steps")

    @property
    def offset(self) -> float:
        if self.qber_offset is not None:
            return self.qber_offset
        if self.magnitude is not None:
            return self.magnitude
        return 0.08


@router.get("/current", response_model=QKDMetrics, summary="Get current QKD communication performance metrics")
async def get_current_qkd() -> QKDMetrics:
    """Return latest QKD state: QBER, raw rate, sifted rate, asymptotic SKR, channel loss, and root-cause breakdown."""
    return qkd_service.get_metrics()


@router.post("/anomaly", summary="Inject simulated security anomaly component")
@router.post("/inject-anomaly", summary="Inject simulated security anomaly component (alias)")
async def inject_anomaly(payload: AnomalyRequest):
    """Simulate eavesdropping attack or quantum channel physical fault by injecting QBER."""
    offset = payload.offset
    qkd_service.inject_anomaly(offset)
    return {"status": "success", "injected_qber_offset": offset, "anomaly_type": payload.anomaly_type}


@router.delete("/anomaly", summary="Clear active security anomaly injection")
@router.post("/clear-anomaly", summary="Clear active security anomaly injection (POST alias)")
async def clear_anomaly():
    """Reset security anomaly injection back to 0.0."""
    qkd_service.clear_anomaly()
    return {"status": "success", "message": "Anomaly injection cleared"}
