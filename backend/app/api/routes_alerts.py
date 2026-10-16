"""Alerts API routes for monitoring system degradation and security events."""

from typing import List
from fastapi import APIRouter
from backend.app.models.alerts import Alert
from backend.app.services.alert_service import alert_service

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get("", response_model=List[Alert], summary="Get active operational and security alerts")
async def get_alerts() -> List[Alert]:
    """Return all currently active alerts across QBER, path loss, mount vibration, and security."""
    return alert_service.get_active_alerts()
