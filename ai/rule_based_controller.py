"""RuleBasedController: Expert heuristic baseline controller for optical quantum links.

Adjusts transmission power, photon rate, and beam divergence dynamically based on
link loss, QBER, mount vibration, and solar background noise while enforcing
rate-of-change safety limits.
"""

import numpy as np

from backend.app.config import settings
from backend.app.models.control import ControlAction
from backend.app.models.environment import EnvironmentData
from backend.app.models.qkd import OpticalChannelState, QKDMetrics
from backend.app.models.satellite import SatelliteState


class RuleBasedController:
    """Deterministic heuristic controller acting as empirical baseline."""

    def __init__(
        self,
        max_rate_of_change: float = 0.20,
        min_power: float = 5.0,
        max_power: float = 100.0,
        min_photon_rate: float = 0.05,
        max_photon_rate: float = 1.0,
        min_divergence: float = 0.10,
        max_divergence: float = 1.0
    ):
        self.max_rate_of_change = max_rate_of_change
        self.min_power = min_power
        self.max_power = max_power
        self.min_photon_rate = min_photon_rate
        self.max_photon_rate = max_photon_rate
        self.min_divergence = min_divergence
        self.max_divergence = max_divergence

        # Initial nominal state
        self.current_action = ControlAction(
            transmission_power_pct=50.0,
            photon_rate_norm=0.70,
            beam_divergence_norm=0.25,
            controller_type="RULE_BASED",
            reason="Initialized to nominal baseline"
        )

    def decide(
        self,
        satellite: SatelliteState,
        environment: EnvironmentData,
        channel: OpticalChannelState,
        qkd: QKDMetrics
    ) -> ControlAction:
        """Compute next control action using heuristic rule hierarchy with rate-limiting."""
        # Rule 0: If satellite is below horizon, power down into standby
        if not satellite.is_visible or satellite.elevation_deg < settings.MIN_ELEVATION:
            target_power = self.min_power
            target_rate = self.min_photon_rate
            target_div = 0.30
            reason = "Satellite below line-of-sight cutoff; standby mode active"
            return self._apply_rate_limit(target_power, target_rate, target_div, reason)

        target_power = self.current_action.transmission_power_pct
        target_rate = self.current_action.photon_rate_norm
        target_div = self.current_action.beam_divergence_norm
        reasons = []

        # Rule 1: High mount vibration -> widen beam divergence to mitigate pointing loss
        if environment.vibration > 0.40:
            target_div = min(self.max_divergence, 0.25 + 0.50 * environment.vibration)
            reasons.append(f"High vibration ({environment.vibration:.2f}g) -> widened beam divergence")
        else:
            # Low vibration -> narrow beam divergence to minimize geometric diffraction loss
            target_div = max(self.min_divergence, 0.15)

        # Rule 2: High Ambient Light / Low SNR -> boost power and photon rate
        if environment.ambient_light > 40000.0 or channel.snr_db < 6.0:
            target_power = min(self.max_power, target_power + 25.0)
            target_rate = min(self.max_photon_rate, 0.90)
            reasons.append("High ambient noise -> increased transmission power and photon rate")

        # Rule 3: High Channel Path Loss (> 28 dB) -> boost power
        if channel.total_loss_db > 28.0:
            target_power = min(self.max_power, target_power + 20.0)
            reasons.append(f"Elevated path loss ({channel.total_loss_db:.1f}dB) -> boosted laser power")

        # Rule 4: Elevated QBER (> 6%)
        if qkd.qber > 0.06:
            if environment.vibration > 0.40:
                target_div = min(self.max_divergence, target_div + 0.15)
            # If QBER is approaching critical threshold (9%), slightly moderate photon rate
            if qkd.qber > 0.09:
                target_rate = max(self.min_photon_rate, target_rate - 0.15)
                reasons.append("Critical QBER -> moderated photon rate to suppress multi-photon emissions")

        # Rule 5: Optimal Conditions (QBER < 2.5%, Low Loss, High SKR) -> Conserve energy
        if qkd.qber < 0.025 and channel.total_loss_db < 22.0 and qkd.secret_key_rate > 1000.0:
            target_power = max(self.min_power + 15.0, target_power - 10.0)
            reasons.append("Channel optimal -> energy conservation throttle active")

        if not reasons:
            reasons.append("Nominal tracking state maintained")

        combined_reason = "; ".join(reasons)
        return self._apply_rate_limit(target_power, target_rate, target_div, combined_reason)

    def _apply_rate_limit(
        self,
        target_power: float,
        target_rate: float,
        target_div: float,
        reason: str
    ) -> ControlAction:
        """Enforce maximum delta per timestep and absolute hardware constraints."""
        # Rate-of-change clamping
        max_delta_power = self.max_rate_of_change * 100.0  # e.g. 20%
        delta_p = np.clip(target_power - self.current_action.transmission_power_pct, -max_delta_power, max_delta_power)
        new_power = float(np.clip(
            self.current_action.transmission_power_pct + delta_p,
            self.min_power, self.max_power
        ))

        delta_r = np.clip(target_rate - self.current_action.photon_rate_norm, -self.max_rate_of_change, self.max_rate_of_change)
        new_rate = float(np.clip(
            self.current_action.photon_rate_norm + delta_r,
            self.min_photon_rate, self.max_photon_rate
        ))

        delta_d = np.clip(target_div - self.current_action.beam_divergence_norm, -self.max_rate_of_change, self.max_rate_of_change)
        new_div = float(np.clip(
            self.current_action.beam_divergence_norm + delta_d,
            self.min_divergence, self.max_divergence
        ))

        self.current_action = ControlAction(
            transmission_power_pct=round(new_power, 2),
            photon_rate_norm=round(new_rate, 4),
            beam_divergence_norm=round(new_div, 4),
            controller_type="RULE_BASED",
            reason=reason
        )
        return self.current_action

    def reset(self) -> ControlAction:
        """Reset controller to default baseline."""
        self.current_action = ControlAction(
            transmission_power_pct=50.0,
            photon_rate_norm=0.70,
            beam_divergence_norm=0.25,
            controller_type="RULE_BASED",
            reason="Reset to default baseline"
        )
        return self.current_action
