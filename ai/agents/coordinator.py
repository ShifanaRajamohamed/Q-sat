"""Coordinator Agent: Hierarchical decision maker that resolves agent conflicts and executes final control actions."""

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

    def __init__(self, max_rate_of_change: float = 0.20):
        self.weather_agent = WeatherAgent()
        self.comm_agent = CommunicationAgent()
        self.security_agent = SecurityAgent()

        self.max_rate_of_change = max_rate_of_change

        # Current state
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
        # 1. Individual domain assessments
        weather_dec = self.weather_agent.analyze(environment)
        comm_dec = self.comm_agent.analyze(satellite, channel, qkd)
        security_dec = self.security_agent.analyze(environment, channel, qkd)

        # 2. Conflict Detection & Arbitration
        conflict = False
        notes = []

        if not satellite.is_visible or satellite.elevation_deg < settings.MIN_ELEVATION:
            target_power = settings.MIN_TRANSMISSION_POWER
            target_rate = settings.MIN_PHOTON_RATE
            target_div = 0.30
            notes.append("Link unavailable; setting standby power")
        else:
            target_power = comm_dec.target_power_pct
            target_rate = comm_dec.target_photon_rate_norm
            target_div = 0.20

            # Rule Conflict A: Comm wants high power/rate, but Weather reports Severe conditions
            if weather_dec.severity in ["HIGH", "SEVERE"] and comm_dec.target_power_pct > 80.0:
                conflict = True
                # Compromise: moderate power to avoid burning thermal dissipation during severe attenuation
                target_power = min(85.0, comm_dec.target_power_pct * 0.90)
                target_rate = min(0.75, target_rate * 0.85)
                notes.append("Arbitrated Comm vs Weather: Moderated transmission aggressiveness due to severe atmospheric extinction.")

            # Rule Conflict B: Security flags Anomaly vs Comm wants maximum throughput
            if security_dec.classification == "ANOMALY":
                conflict = True
                # Security overrides: apply conservative rate, increase divergence
                target_rate = min(0.50, target_rate * 0.60)
                target_div = min(1.0, target_div * security_dec.recommended_divergence_adj)
                notes.append("Security Alert: Anomaly detected! Scaled down photon rate and broadened beam divergence for spatial validation.")

            # Rule Conflict C: Platform Mount Vibration
            if environment.vibration > 0.40:
                target_div = min(1.0, max(target_div, 0.25 + 0.45 * environment.vibration))
                notes.append("Compensated platform mount vibration via expanded beam spot.")

            # Default nominal
            if not notes:
                notes.append("All agent recommendations aligned; nominal optimization active.")

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
