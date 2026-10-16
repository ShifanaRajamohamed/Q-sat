"""Unit tests for Phase 6: Rule-Based Controller."""

import pytest
from backend.app.models.environment import EnvironmentData
from backend.app.models.qkd import OpticalChannelState, QKDMetrics
from backend.app.models.satellite import SatelliteState
from ai.rule_based_controller import RuleBasedController


@pytest.fixture
def base_sat():
    return SatelliteState(
        timestamp=100.0, satellite_name="Q-SAT-1", altitude_km=500.0,
        latitude=10.79, longitude=78.70, azimuth_deg=180.0, elevation_deg=45.0,
        slant_range_km=680.0, orbital_velocity_km_s=7.61, is_visible=True,
        pass_progress=0.5, link_status="TRACKING", pass_id=1
    )


def test_rule_based_standby_when_below_horizon(base_sat):
    """Verify controller stands by at minimum power when satellite is below horizon."""
    ctrl = RuleBasedController()
    sat_down = base_sat.model_copy(update={"is_visible": False, "elevation_deg": -5.0})
    env = EnvironmentData(
        timestamp=0.0, temperature=25.0, humidity=50.0, ambient_light=500.0,
        vibration=0.02, cloud_factor=0.05, turbulence=0.10, data_source="SIMULATION"
    )
    channel = OpticalChannelState(
        total_loss_db=100.0, transmittance=0.0, fspl_loss_db=60.0, atmospheric_loss_db=40.0,
        pointing_loss_db=0.0, scintillation_loss_db=0.0, received_photon_rate=0.0,
        background_noise_rate=500.0, snr_db=-99.0, beam_spot_radius_m=1000.0
    )
    qkd = QKDMetrics(
        timestamp=0.0, transmitted_photon_rate=50e6, received_photon_rate=0.0,
        raw_key_rate=0.0, sifted_key_rate=0.0, qber=0.50, secret_key_rate=0.0,
        qber_decomposition={"base_error": 0.01, "atmospheric_noise": 0.1, "background_light_noise": 0.1,
                            "pointing_error": 0.1, "detector_noise": 0.1, "security_anomaly_component": 0.0,
                            "total_qber": 0.50},
        channel_loss_db=100.0, channel_transmittance=0.0, is_key_distillation_possible=False,
        status_label="LINK_DOWN"
    )

    # Step several times to allow rate limiter to power down
    for _ in range(5):
        action = ctrl.decide(sat_down, env, channel, qkd)

    assert action.transmission_power_pct == pytest.approx(ctrl.min_power, abs=1.0)
    assert action.photon_rate_norm == pytest.approx(ctrl.min_photon_rate, abs=0.05)


def test_rule_based_vibration_adaptation(base_sat):
    """Verify high vibration prompts widening beam divergence."""
    ctrl = RuleBasedController()
    high_vib_env = EnvironmentData(
        timestamp=0.0, temperature=25.0, humidity=50.0, ambient_light=500.0,
        vibration=1.20, cloud_factor=0.05, turbulence=0.10, data_source="SIMULATION"
    )
    channel = OpticalChannelState(
        total_loss_db=25.0, transmittance=0.003, fspl_loss_db=18.0, atmospheric_loss_db=3.0,
        pointing_loss_db=4.0, scintillation_loss_db=0.0, received_photon_rate=20000.0,
        background_noise_rate=500.0, snr_db=16.0, beam_spot_radius_m=15.0
    )
    qkd = QKDMetrics(
        timestamp=0.0, transmitted_photon_rate=50e6, received_photon_rate=20000.0,
        raw_key_rate=2000.0, sifted_key_rate=1000.0, qber=0.07, secret_key_rate=250.0,
        qber_decomposition={"base_error": 0.01, "atmospheric_noise": 0.01, "background_light_noise": 0.01,
                            "pointing_error": 0.03, "detector_noise": 0.01, "security_anomaly_component": 0.0,
                            "total_qber": 0.07},
        channel_loss_db=25.0, channel_transmittance=0.003, is_key_distillation_possible=True,
        status_label="DEGRADED"
    )

    action1 = ctrl.decide(base_sat, high_vib_env, channel, qkd)
    assert "vibration" in action1.reason.lower()
    # Beam divergence should be expanding to counter jitter
    assert action1.beam_divergence_norm > 0.25
