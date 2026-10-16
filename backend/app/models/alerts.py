"""Pydantic models for Real-Time System and Security Alerts."""

from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field


class Alert(BaseModel):
    """System, operational, or security alert notification."""
    id: str = Field(..., description="Unique alert identifier")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    severity: Literal["INFO", "WARNING", "CRITICAL"] = Field("INFO", description="Alert urgency tier")
    category: Literal["QBER", "KEY_RATE", "OPTICAL_CHANNEL", "ENVIRONMENT", "SECURITY", "SATELLITE"] = Field(
        ..., description="Alert subsystem category"
    )
    title: str = Field(..., description="Short alert title")
    message: str = Field(..., description="Descriptive alert detail")
    is_active: bool = Field(True, description="True if alert condition is currently unresolved")
