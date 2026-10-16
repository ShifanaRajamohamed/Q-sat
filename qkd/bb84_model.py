"""BB84 Analytical Model: Evaluates error attribution and key distillation efficiency."""

from typing import Optional
from backend.app.config import settings
from backend.app.models.environment import EnvironmentData
from backend.app.models.qkd import OpticalChannelState, QKDMetrics
from qkd.key_rate import calculate_raw_key_rate, calculate_sifted_key_rate
from qkd.qber import calculate_qber
from qkd.secret_key_rate import calculate_secret_key_rate


class BB84Model:
    """Evaluates BB84 analytical QKD metrics given optical channel state and environment."""

    def __init__(
        self,
        detector_efficiency: float = 0.10,
        basis_matching_prob: float = 0.50,
        error_correction_efficiency: float = 1.16,
        qber_security_threshold: float = 0.110
    ):
        self.detector_efficiency = detector_efficiency
        self.basis_matching_prob = basis_matching_prob
        self.error_correction_efficiency = error_correction_efficiency
        self.qber_security_threshold = qber_security_threshold

    def evaluate(
        self,
        channel_state: OpticalChannelState,
        environment: EnvironmentData,
        timestamp: float,
        anomaly_component: float = 0.0
    ) -> QKDMetrics:
        """Calculate complete BB84 QKD metrics and return strongly-typed QKDMetrics object."""
        # 1. Error Rate Attribution
        qber_decomp = calculate_qber(
            channel_state=channel_state,
            environment=environment,
            anomaly_component=anomaly_component
        )
        total_qber = qber_decomp.total_qber

        # 2. Key Generation Rates
        raw_rate = calculate_raw_key_rate(
            received_photon_rate=channel_state.received_photon_rate,
            detector_efficiency=self.detector_efficiency
        )
        sifted_rate = calculate_sifted_key_rate(
            raw_key_rate=raw_rate,
            basis_matching_probability=self.basis_matching_prob
        )

        # 3. Asymptotic Secret Key Rate
        skr, sec_fraction, is_secure = calculate_secret_key_rate(
            sifted_key_rate=sifted_rate,
            qber=total_qber,
            error_correction_efficiency=self.error_correction_efficiency,
            qber_threshold=self.qber_security_threshold
        )

        # 4. Status determination
        if channel_state.transmittance <= 1e-8 or channel_state.received_photon_rate <= 0.0:
            status_label = "LINK_DOWN"
        elif total_qber >= self.qber_security_threshold:
            status_label = "CRITICAL_QBER"
        elif total_qber > 0.05 or channel_state.total_loss_db > 35.0:
            status_label = "DEGRADED"
        else:
            status_label = "OPTIMAL"

        base_tx_rate = 50e6  # 50 MHz base rate
        return QKDMetrics(
            timestamp=round(timestamp, 3),
            transmitted_photon_rate=round(base_tx_rate, 1),
            received_photon_rate=round(channel_state.received_photon_rate, 2),
            raw_key_rate=round(raw_rate, 2),
            sifted_key_rate=round(sifted_rate, 2),
            qber=round(total_qber, 4),
            secret_key_rate=round(skr, 2),
            qber_decomposition=qber_decomp,
            channel_loss_db=round(channel_state.total_loss_db, 2),
            channel_transmittance=round(channel_state.transmittance, 8),
            is_key_distillation_possible=is_secure,
            status_label=status_label
        )
