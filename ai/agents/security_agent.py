"""Security & Anomaly Agent: Distinguishes physical environmental channel degradation from potential security anomalies."""

from typing import List
import numpy as np

from backend.app.models.agents import SecurityAgentDecision
from backend.app.models.environment import EnvironmentData
from backend.app.models.qkd import OpticalChannelState, QKDMetrics


class SecurityAgent:
    """Classifies root cause of QBER elevation: physical degradation vs potential eavesdropping anomaly."""

    def __init__(self, history_len: int = 20):
        self.qber_history: List[float] = []
        self.history_len = history_len

    def analyze(
        self,
        environment: EnvironmentData,
        channel: OpticalChannelState,
        qkd: QKDMetrics
    ) -> SecurityAgentDecision:
        """Perform multi-factor attribution on observed QBER."""
        self.qber_history.append(qkd.qber)
        if len(self.qber_history) > self.history_len:
            self.qber_history.pop(0)

        decomp = qkd.qber_decomposition
        if isinstance(decomp, dict):
            from backend.app.models.qkd import QBERDecomposition
            decomp = QBERDecomposition(**decomp)

        # Total noise accounted for by modeled physical phenomena
        explained_physical_error = (
            decomp.base_error +
            decomp.atmospheric_noise +
            decomp.background_light_noise +
            decomp.pointing_error +
            decomp.detector_noise
        )

        unexplained_error = max(0.0, qkd.qber - explained_physical_error)

        # Identify leading physical noise component
        components = {
            "Ambient Stray Light": decomp.background_light_noise,
            "Platform Mount Vibration": decomp.pointing_error,
            "Atmospheric Turbulence": decomp.atmospheric_noise,
            "Detector Dark Counts": decomp.detector_noise,
            "Baseline Optical Misalignment": decomp.base_error
        }
        primary_driver = max(components.items(), key=lambda item: item[1])[0]

        # Classification Logic
        if unexplained_error > 0.035 or decomp.security_anomaly_component > 0.02:
            # Unexplained excess error -> potential eavesdropping disturbance (intercept-resend) or hardware fault
            classification = "ANOMALY"
            prob = min(0.98, 0.50 + unexplained_error * 8.0)
            explanation = (
                f"ALERT: Observed QBER ({qkd.qber*100:.2f}%) exceeds physically explained noise "
                f"({explained_physical_error*100:.2f}%) by {unexplained_error*100:.2f}%. "
                f"Potential intercept-resend eavesdropping or unauthorized optical perturbation."
            )
            div_adj = 1.30  # Expand divergence to detect spatial beam clipping
            conf = 0.90

        elif qkd.qber > 0.055:
            # High error, but fully accounted for by physical phenomena
            classification = "DEGRADED"
            prob = min(0.20, unexplained_error * 2.0)
            explanation = (
                f"Elevated QBER ({qkd.qber*100:.2f}%) is accounted for by physical factors. "
                f"Dominant contributor: {primary_driver} ({components[primary_driver]*100:.2f}% error). "
                f"No evidence of cryptographic intercept."
            )
            div_adj = 1.15 if primary_driver == "Platform Mount Vibration" else 1.0
            conf = 0.88

        else:
            # Normal baseline conditions
            classification = "NORMAL"
            prob = 0.02
            explanation = f"Channel nominal. QBER is within normal baseline limits ({qkd.qber*100:.2f}%)."
            div_adj = 1.0
            conf = 0.95

        return SecurityAgentDecision(
            classification=classification,
            anomaly_probability=round(float(prob), 3),
            primary_error_driver=primary_driver if classification != "ANOMALY" else "Unexplained Excess QBER",
            root_cause_explanation=explanation,
            recommended_divergence_adj=div_adj,
            confidence=conf
        )
