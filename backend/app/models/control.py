"""Pydantic models for Ground Station Control Actions and Controller Telemetry."""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class ControlAction(BaseModel):
    """Ground station transmission control parameters."""
    transmission_power_pct: float = Field(..., ge=0.0, le=100.0, description="Laser transmission power percentage (0 - 100%)")
    photon_rate_norm: float = Field(..., ge=0.0, le=1.0, description="Normalized photon emission pulse rate [0.0 to 1.0]")
    beam_divergence_norm: float = Field(..., ge=0.0, le=1.0, description="Normalized optical beam divergence [0.0 to 1.0]")
    controller_type: Literal["STATIC", "RULE_BASED", "PPO", "MULTI_AGENT"] = Field(
        "RULE_BASED", description="Active controller paradigm"
    )
    reason: str = Field("Nominal operation", description="Human-readable decision explanation")


class ControlDelta(BaseModel):
    """Change in control actions relative to previous timestep."""
    delta_power_pct: float
    delta_photon_rate: float
    delta_beam_divergence: float
    controller_type: str
    reason: str
    previous_action: ControlAction
    new_action: ControlAction
