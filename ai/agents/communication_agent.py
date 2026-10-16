"""Communication Agent: Evaluates optical link margin, geometry, and key throughput."""

from backend.app.models.agents import CommunicationAgentDecision
from backend.app.models.qkd import OpticalChannelState, QKDMetrics
from backend.app.models.satellite import SatelliteState


class CommunicationAgent:
    """Specialized agent optimizing photon rate, laser power, and link margin."""

    def analyze(
        self,
        satellite: SatelliteState,
        channel: OpticalChannelState,
        qkd: QKDMetrics
    ) -> CommunicationAgentDecision:
        """Evaluate line-of-sight elevation, path loss, and secret key generation efficiency."""
        if not satellite.is_visible or satellite.elevation_deg < 10.0:
            return CommunicationAgentDecision(
                link_viability="DISCONNECTED",
                link_margin_db=-30.0,
                target_power_pct=5.0,
                target_photon_rate_norm=0.05,
                recommendation="Target is below line-of-sight horizon; hold actuators in standby",
                confidence=0.99
            )

        # Baseline threshold is ~32 dB loss for viable single-photon link
        link_margin_db = 32.0 - channel.total_loss_db

        if channel.total_loss_db > 36.0 or qkd.qber > 0.10:
            link_viability = "MARGINAL"
            target_power = 95.0
            target_rate = 0.85
            rec = "Link margin degraded; maximize transmission power to maintain detectable photon rate"
            conf = 0.84
        elif channel.total_loss_db < 24.0 and qkd.qber < 0.03:
            link_viability = "OPTIMAL"
            target_power = 55.0  # Conserve energy
            target_rate = 0.90
            rec = "Link margin healthy (>8 dB); throttle power down to optimize energy efficiency"
            conf = 0.92
        else:
            link_viability = "OPTIMAL"
            target_power = 75.0
            target_rate = 0.80
            rec = "Standard tracking link operating nominally"
            conf = 0.88

        return CommunicationAgentDecision(
            link_viability=link_viability,
            link_margin_db=round(float(link_margin_db), 2),
            target_power_pct=round(float(target_power), 1),
            target_photon_rate_norm=round(float(target_rate), 3),
            recommendation=rec,
            confidence=conf
        )
