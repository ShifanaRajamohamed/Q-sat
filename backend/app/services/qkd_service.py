"""QKD Service: Centralized manager for analytical QKD simulation."""

import logging
from typing import Optional
from backend.app.models.environment import EnvironmentData
from backend.app.models.qkd import OpticalChannelState, QKDMetrics
from backend.app.models.satellite import SatelliteState
from backend.app.services.environment_service import environment_service
from backend.app.services.satellite_service import satellite_service
from digital_twin.optical_channel import OpticalChannelModel
from qkd.qkd_simulator import QKDSimulator

logger = logging.getLogger("qsat.qkd_service")


class QKDService:
    """Computes and exposes QKD communication metrics linked to active Digital Twin states."""

    def __init__(self):
        self.simulator = QKDSimulator()
        self.optical_channel = OpticalChannelModel()
        self.latest_channel_state: Optional[OpticalChannelState] = None
        self.latest_metrics: Optional[QKDMetrics] = None

    def evaluate_current(
        self,
        transmission_power_pct: float = 100.0,
        photon_rate_norm: float = 1.0,
        beam_divergence_norm: float = 0.20
    ) -> QKDMetrics:
        """Evaluate QKD metrics using current satellite and environmental states."""
        sat_state: SatelliteState = satellite_service.get_state()
        env_state: EnvironmentData = environment_service.get_current_environment()

        # Compute optical channel state
        self.latest_channel_state = self.optical_channel.calculate_link_state(
            satellite=sat_state,
            environment=env_state,
            transmission_power_pct=transmission_power_pct,
            photon_rate_norm=photon_rate_norm,
            beam_divergence_norm=beam_divergence_norm
        )

        # Compute BB84 metrics
        self.latest_metrics = self.simulator.step(
            channel_state=self.latest_channel_state,
            environment=env_state,
            timestamp=sat_state.timestamp
        )
        return self.latest_metrics

    def get_metrics(self) -> QKDMetrics:
        """Return latest metrics or compute on-demand."""
        if self.latest_metrics is None:
            return self.evaluate_current()
        return self.latest_metrics

    def inject_anomaly(self, qber_offset: float) -> None:
        """Inject simulated anomalous error and immediately recompute metrics."""
        self.simulator.inject_security_anomaly(qber_offset)
        logger.warning("Injected security anomaly QBER component: +%.4f", qber_offset)
        self.evaluate_current()

    def clear_anomaly(self) -> None:
        """Clear anomaly injection and immediately recompute metrics."""
        self.simulator.clear_anomaly()
        logger.info("Cleared security anomaly injection")
        self.evaluate_current()


# Global singleton instance
qkd_service = QKDService()
