"""Pydantic models for the Hierarchical Multi-Agent System."""

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from backend.app.models.control import ControlAction


class WeatherAgentDecision(BaseModel):
    """Assessment from the Weather/Atmospheric Agent."""
    severity: Literal["LOW", "MODERATE", "HIGH", "SEVERE"] = Field(..., description="Overall weather severity level")
    cloud_impact: float = Field(..., ge=0.0, le=1.0, description="Estimated optical cloud extinction impact")
    turbulence_impact: float = Field(..., ge=0.0, le=1.0, description="Estimated scintillation fading impact")
    ambient_noise_level: Literal["NEGLIGIBLE", "MODERATE", "SATURATED"] = Field(..., description="Solar stray light tier")
    recommendation: str = Field(..., description="Operating condition guidance")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score [0.0 to 1.0]")


class CommunicationAgentDecision(BaseModel):
    """Assessment and proposed actuator targets from the Communication Link Agent."""
    link_viability: Literal["DISCONNECTED", "MARGINAL", "OPTIMAL"] = Field(..., description="Link viability status")
    link_margin_db: float = Field(..., description="Estimated link margin relative to threshold (dB)")
    target_power_pct: float = Field(..., ge=0.0, le=100.0, description="Target laser transmission power (%)")
    target_photon_rate_norm: float = Field(..., ge=0.0, le=1.0, description="Target normalized photon rate")
    recommendation: str = Field(..., description="Link optimization recommendation")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score [0.0 to 1.0]")


class SecurityAgentDecision(BaseModel):
    """Assessment of channel anomalies from the Security/Anomaly Agent."""
    classification: Literal["NORMAL", "DEGRADED", "ANOMALY"] = Field(..., description="Security assessment classification")
    anomaly_probability: float = Field(..., ge=0.0, le=1.0, description="Assessed probability of malicious or unexplained disturbance")
    primary_error_driver: str = Field(..., description="Physical or anomalous factor predominantly driving QBER")
    root_cause_explanation: str = Field(..., description="Detailed diagnostic breakdown")
    recommended_divergence_adj: float = Field(1.0, description="Recommended multiplier for beam divergence")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score [0.0 to 1.0]")


class CoordinatorDecision(BaseModel):
    """Final arbitration and conflict-resolution output from the Coordinator Agent."""
    timestamp: float
    final_action: ControlAction
    conflict_detected: bool
    conflict_resolution_notes: str
    weather_agent: WeatherAgentDecision
    communication_agent: CommunicationAgentDecision
    security_agent: SecurityAgentDecision
