"""Coordinator Agent: Hierarchical rule-arbitrated multi-agent controller.

Note on Architecture:
This system uses a hierarchical domain-expert heuristic and rule-arbitration architecture.
It is explicitly NOT Multi-Agent Reinforcement Learning (MARL). Domain recommendations
from Weather, Comm, and Security agents are synthesized with rate-of-change constraints.

Supports selective ablation of individual agents (Weather, Comm, Security) to enable
fair ablation studies against baseline arbitration.
"""

from typing import List, Optional
import numpy as np

from backend.app.config import settings
from backend.app.models.agents import (
    CommunicationAgentDecision,
    CoordinatorDecision,
    SecurityAgentDecision,
    WeatherAgentDecision,
)
from backend.app.models.control import ControlAction
from backend.app.models.environment import EnvironmentData
from backend.app.models.qkd import OpticalChannelState, QKDMetrics
from backend.app.models.satellite import SatelliteState
from ai.agents.communication_agent import CommunicationAgent
from ai.agents.security_agent import SecurityAgent
from ai.agents.weather_agent import WeatherAgent


class CoordinatorAgent:
    """Arbitrates and synthesizes domain recommendations from Weather, Comm, and Security agents."""

    def __init__(
        self,
        enable_weather: bool = True,
        enable_comm: bool = True,
        enable_security: bool = True,
        max_rate_of_change: float = 0.20
    ):
        self.enable_weather = enable_weather
        self.enable_comm = enable_comm
        self.enable_security = enable_security
        self.max_rate_of_change = max_rate_of_change

        self.weather_agent = WeatherAgent() if enable_weather else None
        self.comm_agent = CommunicationAgent() if enable_comm else None
        self.security_agent = SecurityAgent() if enable_security else None

        # Current actuator state
        self.power_pct: float = 50.0
        self.photon_rate_norm: float = 0.70
        self.beam_divergence_norm: float = 0.25

    def step(
        self,
        satellite: SatelliteState,
        environment: EnvironmentData,
        channel: OpticalChannelState,
        qkd: QKDMetrics
    ) -> CoordinatorDecision:
        """Run hierarchical decision flow: Weather -> Comm -> Security -> Arbitration."""
        # 1. Individual domain assessments (with fallback defaults if ablated)
        weather_dec = (
            self.weather_agent.analyze(environment)
            if self.enable_weather and self.weather_agent
            else WeatherAgentDecision(
                severity="LOW",
                cloud_impact=0.0,
                turbulence_impact=0.0,
                ambient_noise_level="NEGLIGIBLE",
                recommendation="Weather agent ablated/disabled; using baseline assumptions.",
                confidence=1.0
            )
        )

        comm_dec = (
            self.comm_agent.analyze(satellite, channel, qkd)
            if self.enable_comm and self.comm_agent
            else CommunicationAgentDecision(
                link_viability="OPTIMAL",
                link_margin_db=5.0,
                target_power_pct=50.0,
                target_photon_rate_norm=0.70,
                recommendation="Communication agent ablated/disabled; using fixed static target.",
                confidence=1.0
            )
        )

        security_dec = (
            self.security_agent.analyze(environment, channel, qkd)
            if self.enable_security and self.security_agent
            else SecurityAgentDecision(
                classification="NORMAL",
                anomaly_probability=0.0,
                primary_error_driver="Ablated Baseline",
                root_cause_explanation="Security agent ablated/disabled; no anomaly monitoring.",
                recommended_divergence_adj=1.0,
                confidence=1.0
            )
        )

        # 2. Conflict Detection & Arbitration Logic
        conflict = False
        notes: List[str] = []

        if not satellite.is_visible or satellite.elevation_deg < settings.MIN_ELEVATION:
            target_power = settings.MIN_TRANSMISSION_POWER
            target_rate = settings.MIN_PHOTON_RATE
            target_div = 0.30
            notes.append("Link unavailable (satellite below horizon); setting transmitter to standby")
        else:
            target_power = comm_dec.target_power_pct
            target_rate = comm_dec.target_photon_rate_norm
            target_div = 0.20

            # Rule Conflict A: Comm wants high power/rate, but Weather reports severe attenuation
            if self.enable_weather and weather_dec.severity in ["HIGH", "SEVERE"] and comm_dec.target_power_pct > 80.0:
                conflict = True
                target_power = min(85.0, comm_dec.target_power_pct * 0.90)
                target_rate = min(0.75, target_rate * 0.85)
                notes.append("Arbitration (Comm vs Weather): Moderated power and rate to prevent thermal dissipation during severe attenuation")

            # Rule Conflict B: Security flags Modeled Anomaly vs Comm wants maximum throughput
            if self.enable_security and security_dec.classification == "ANOMALY":
                conflict = True
                target_rate = min(0.50, target_rate * 0.60)
                target_div = min(1.0, target_div * security_dec.recommended_divergence_adj)
                notes.append("Arbitration (Security Override): Modeled anomaly detected; throttled photon rate and broadened divergence for spatial validation")

            # Platform Mount Vibration Compensation
            if environment.vibration > 0.40:
                target_div = min(1.0, max(target_div, 0.25 + 0.45 * environment.vibration))
                notes.append(f"Compensated platform mount vibration ({environment.vibration:.2f}g) via expanded beam spot")

            if not notes:
                notes.append("All active agent recommendations aligned; nominal optimization active")

        resolution_text = "; ".join(notes)

        # 3. Rate-of-Change Clamping
        max_dp = self.max_rate_of_change * 100.0
        delta_p = float(np.clip(target_power - self.power_pct, -max_dp, max_dp))
        delta_r = float(np.clip(target_rate - self.photon_rate_norm, -self.max_rate_of_change, self.max_rate_of_change))
        delta_d = float(np.clip(target_div - self.beam_divergence_norm, -self.max_rate_of_change, self.max_rate_of_change))

        self.power_pct = float(np.clip(self.power_pct + delta_p, settings.MIN_TRANSMISSION_POWER, settings.MAX_TRANSMISSION_POWER))
        self.photon_rate_norm = float(np.clip(self.photon_rate_norm + delta_r, settings.MIN_PHOTON_RATE, settings.MAX_PHOTON_RATE))
        self.beam_divergence_norm = float(np.clip(self.beam_divergence_norm + delta_d, settings.MIN_BEAM_DIVERGENCE, settings.MAX_BEAM_DIVERGENCE))

        final_action = ControlAction(
            transmission_power_pct=round(self.power_pct, 2),
            photon_rate_norm=round(self.photon_rate_norm, 4),
            beam_divergence_norm=round(self.beam_divergence_norm, 4),
            controller_type="MULTI_AGENT",
            reason=resolution_text
        )

        return CoordinatorDecision(
            timestamp=round(satellite.timestamp, 3),
            final_action=final_action,
            conflict_detected=conflict,
            conflict_resolution_notes=resolution_text,
            weather_agent=weather_dec,
            communication_agent=comm_dec,
            security_agent=security_dec
        )
