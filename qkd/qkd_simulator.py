"""QKDSimulator: High-level simulator state manager for quantum key distillation."""

from typing import Optional
from backend.app.config import settings
from backend.app.models.environment import EnvironmentData
from backend.app.models.qkd import OpticalChannelState, QKDMetrics
from qkd.bb84_model import BB84Model


class QKDSimulator:
    """Stateful simulation manager for BB84-inspired quantum communication."""

    def __init__(
        self,
        detector_efficiency: Optional[float] = None,
        basis_matching_prob: Optional[float] = None,
        error_correction_efficiency: Optional[float] = None
    ):
        self.bb84_model = BB84Model(
            detector_efficiency=detector_efficiency or settings.QKD_DETECTOR_EFFICIENCY,
            basis_matching_prob=basis_matching_prob or settings.BASIS_MATCHING_PROBABILITY,
            error_correction_efficiency=error_correction_efficiency or settings.ERROR_CORRECTION_EFFICIENCY
        )
        self.anomaly_injection: float = 0.0
        self.latest_metrics: Optional[QKDMetrics] = None

    def inject_security_anomaly(self, anomaly_qber: float) -> None:
        """Inject simulated anomalous error (e.g. eavesdropping disturbance or optical fault)."""
        self.anomaly_injection = max(0.0, min(0.40, anomaly_qber))

    def clear_anomaly(self) -> None:
        """Clear active anomaly injection."""
        self.anomaly_injection = 0.0

    def step(
        self,
        channel_state: OpticalChannelState,
        environment: EnvironmentData,
        timestamp: float
    ) -> QKDMetrics:
        """Evaluate QKD performance at the current time step."""
        self.latest_metrics = self.bb84_model.evaluate(
            channel_state=channel_state,
            environment=environment,
            timestamp=timestamp,
            anomaly_component=self.anomaly_injection
        )
        return self.latest_metrics

    def get_metrics(self) -> Optional[QKDMetrics]:
        """Return the latest calculated QKD metrics."""
        return self.latest_metrics
