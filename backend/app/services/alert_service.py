"""Alert Service: Centralized monitor for operational thresholds, channel loss, and security events."""

from datetime import datetime, timezone
from typing import List
from backend.app.models.alerts import Alert
from backend.app.models.environment import EnvironmentData
from backend.app.models.qkd import OpticalChannelState, QKDMetrics
from backend.app.models.satellite import SatelliteState
from backend.app.services.control_service import control_service
from backend.app.services.environment_service import environment_service
from backend.app.services.qkd_service import qkd_service
from backend.app.services.satellite_service import satellite_service


class AlertService:
    """Evaluates telemetry across subsystems and produces active real-time alerts."""

    def get_active_alerts(self) -> List[Alert]:
        alerts: List[Alert] = []
        now_str = datetime.now(timezone.utc).isoformat()

        sat: SatelliteState = satellite_service.get_state()
        env: EnvironmentData = environment_service.get_current_environment()
        qkd: QKDMetrics = qkd_service.get_metrics()
        channel: OpticalChannelState = qkd_service.latest_channel_state

        # 1. Satellite Elevation Cutoff
        if not sat.is_visible:
            alerts.append(Alert(
                id="ALERT-SAT-01",
                timestamp=now_str,
                severity="INFO",
                category="SATELLITE",
                title="Satellite Below Horizon",
                message=f"Satellite elevation is {sat.elevation_deg:.1f}° (below {sat.link_status} threshold). Communication link is idle.",
                is_active=True
            ))

        # 2. Critical or High QBER
        if qkd.qber >= 0.110:
            alerts.append(Alert(
                id="ALERT-QBER-CRIT",
                timestamp=now_str,
                severity="CRITICAL",
                category="QBER",
                title="Critical QBER Threshold Exceeded",
                message=f"QBER has reached {qkd.qber*100:.2f}% (>= 11% cutoff limit). Secret key distillation suspended!",
                is_active=True
            ))
        elif qkd.qber > 0.060:
            alerts.append(Alert(
                id="ALERT-QBER-WARN",
                timestamp=now_str,
                severity="WARNING",
                category="QBER",
                title="Elevated QBER Detected",
                message=f"QBER is elevated at {qkd.qber*100:.2f}%. Actuators compensating.",
                is_active=True
            ))

        # 3. Secret Key Rate (SKR) Low while Visible
        if sat.is_visible and qkd.secret_key_rate <= 100.0:
            alerts.append(Alert(
                id="ALERT-SKR-LOW",
                timestamp=now_str,
                severity="WARNING",
                category="KEY_RATE",
                title="Low Secret Key Rate",
                message=f"Secret key rate is currently degraded at {qkd.secret_key_rate:.1f} bps.",
                is_active=True
            ))

        # 4. High Channel Loss
        if channel and channel.total_loss_db > 32.0 and sat.is_visible:
            alerts.append(Alert(
                id="ALERT-OPT-LOSS",
                timestamp=now_str,
                severity="WARNING",
                category="OPTICAL_CHANNEL",
                title="Severe Channel Path Loss",
                message=f"Total optical path loss is {channel.total_loss_db:.1f} dB. Extreme atmospheric or cloud extinction.",
                is_active=True
            ))

        # 5. High Platform Vibration
        if env.vibration > 0.45:
            alerts.append(Alert(
                id="ALERT-ENV-VIB",
                timestamp=now_str,
                severity="WARNING",
                category="ENVIRONMENT",
                title="High Mount Vibration Jitter",
                message=f"Platform vibration is {env.vibration:.2f} g, inducing telescope pointing jitter.",
                is_active=True
            ))

        # 6. Security Anomaly Detection
        coord_dec = control_service.get_multi_agent_decision()
        if coord_dec and coord_dec.security_agent.classification == "ANOMALY":
            alerts.append(Alert(
                id="ALERT-SEC-ANOMALY",
                timestamp=now_str,
                severity="CRITICAL",
                category="SECURITY",
                title="Potential Security Anomaly Detected",
                message=coord_dec.security_agent.root_cause_explanation,
                is_active=True
            ))

        return alerts


# Global singleton instance
alert_service = AlertService()
