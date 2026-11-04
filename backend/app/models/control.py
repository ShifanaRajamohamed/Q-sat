"""Pydantic models for Ground Station Control Actions and Controller Telemetry."""

from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class ControlAction(BaseModel):
    """Ground station transmission control parameters."""
    transmission_power_pct: float = Field(..., ge=0.0, le=100.0, description="Laser transmission power percentage (0 - 100%)")
    photon_rate_norm: float = Field(..., ge=0.0, le=1.0, description="Normalized photon emission pulse rate [0.0 to 1.0]")
    beam_divergence_norm: float = Field(..., ge=0.0, le=1.0, description="Normalized optical beam divergence [0.0 to 1.0]")
    controller_type: Literal["STATIC", "RULE_BASED", "PPO", "MULTI_AGENT"] = Field(
        "RULE_BASED", description="Active actual controller paradigm"
    )
    requested_controller: Literal["STATIC", "RULE_BASED", "PPO", "MULTI_AGENT"] = Field(
        "RULE_BASED", description="Controller requested by operator or test harness"
    )
    actual_controller: Literal["STATIC", "RULE_BASED", "PPO", "MULTI_AGENT"] = Field(
        "RULE_BASED", description="Controller that produced this decision"
    )
    model_loaded: bool = Field(False, description="True if trained neural model was loaded and utilized")
    fallback_reason: Optional[str] = Field(None, description="Explicit reason if actual != requested")
    reason: str = Field("Nominal operation", description="Human-readable decision explanation")

    @model_validator(mode="before")
    @classmethod
    def sync_controllers(cls, data: dict):
        if isinstance(data, dict):
            # If requested_controller was not provided, sync from controller_type
            ctrl = data.get("controller_type", "RULE_BASED")
            if "requested_controller" not in data:
                data["requested_controller"] = ctrl
            if "actual_controller" not in data:
                data["actual_controller"] = ctrl
            # Ensure controller_type matches actual_controller
            data["controller_type"] = data.get("actual_controller", ctrl)
        return data


class ControlDelta(BaseModel):
    """Change in control actions relative to previous timestep."""
    delta_power_pct: float
    delta_photon_rate: float
    delta_beam_divergence: float
    controller_type: str
    reason: str
    previous_action: ControlAction
    new_action: ControlAction
