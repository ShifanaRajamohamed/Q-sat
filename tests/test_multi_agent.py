"""Unit and integration tests for Phase 9: Hierarchical Multi-Agent Architecture."""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.environment import EnvironmentData
from backend.app.models.qkd import OpticalChannelState, QKDMetrics
from backend.app.models.satellite import SatelliteState
from ai.agents.communication_agent import CommunicationAgent
from ai.agents.coordinator import CoordinatorAgent
from ai.agents.security_agent import SecurityAgent
from ai.agents.weather_agent import WeatherAgent

client = TestClient(app)


@pytest.fixture
def test_setup():
    sat = SatelliteState(
        timestamp=120.0, satellite_name="Q-SAT-1", altitude_km=500.0,
        latitude=10.79, longitude=78.70, azimuth_deg=180.0, elevation_deg=50.0,
        slant_range_km=650.0, orbital_velocity_km_s=7.61, is_visible=True,
        pass_progress=0.5, link_status="TRACKING", pass_id=1
    )
    env = EnvironmentData(
        timestamp=120.0, temperature=25.0, humidity=50.0, ambient_light=800.0,
        vibration=0.02, cloud_factor=0.03, turbulence=0.08, data_source="SIMULATION",
        scenario_name="CLEAR_SKY"
    )
    channel = OpticalChannelState(
        total_loss_db=20.0, transmittance=0.01, fspl_loss_db=16.0, atmospheric_loss_db=2.0,
        pointing_loss_db=1.0, scintillation_loss_db=1.0, received_photon_rate=50000.0,
        background_noise_rate=200.0, snr_db=24.0, beam_spot_radius_m=10.0
    )
    qkd = QKDMetrics(
        timestamp=120.0, transmitted_photon_rate=50e6, received_photon_rate=50000.0,
        raw_key_rate=5000.0, sifted_key_rate=2500.0, qber=0.015, secret_key_rate=1800.0,
        qber_decomposition={"base_error": 0.01, "atmospheric_noise": 0.002, "background_light_noise": 0.001,
                            "pointing_error": 0.001, "detector_noise": 0.001, "security_anomaly_component": 0.0,
                            "total_qber": 0.015},
        channel_loss_db=20.0, channel_transmittance=0.01, is_key_distillation_possible=True,
        status_label="OPTIMAL"
    )
    return sat, env, channel, qkd


def test_weather_agent_assessment(test_setup):
    """Verify Weather Agent correctly classifies clear sky vs severe cloud."""
    sat, env, channel, qkd = test_setup
    agent = WeatherAgent()

    dec_clear = agent.analyze(env)
    assert dec_clear.severity == "LOW"

    # Extreme cloudy environment
    env_cloud = env.model_copy(update={"cloud_factor": 0.90, "turbulence": 0.85})
    dec_severe = agent.analyze(env_cloud)
    assert dec_severe.severity in ["HIGH", "SEVERE"]


def test_security_agent_physical_vs_anomaly(test_setup):
    """Verify Security Agent labels high physical noise as DEGRADED, not ANOMALY."""
    sat, env, channel, qkd = test_setup
    sec_agent = SecurityAgent()

    # Normal case
    dec_norm = sec_agent.analyze(env, channel, qkd)
    assert dec_norm.classification == "NORMAL"

    # Case A: High QBER caused entirely by physical sunlight
    qkd_physical = qkd.model_copy(update={
        "qber": 0.075,
        "qber_decomposition": {"base_error": 0.01, "atmospheric_noise": 0.005,
                               "background_light_noise": 0.055, "pointing_error": 0.002,
                               "detector_noise": 0.003, "security_anomaly_component": 0.0,
                               "total_qber": 0.075}
    })
    dec_physical = sec_agent.analyze(env, channel, qkd_physical)
    # Must NOT be labeled an anomaly since sunlight fully accounts for the QBER!
    assert dec_physical.classification == "DEGRADED"
    assert "Ambient Stray Light" in dec_physical.primary_error_driver

    # Case B: High QBER caused by unexplained excess / anomaly
    qkd_anomaly = qkd.model_copy(update={
        "qber": 0.095,
        "qber_decomposition": {"base_error": 0.01, "atmospheric_noise": 0.005,
                               "background_light_noise": 0.01, "pointing_error": 0.002,
                               "detector_noise": 0.003, "security_anomaly_component": 0.065,
                               "total_qber": 0.095}
    })
    dec_anomaly = sec_agent.analyze(env, channel, qkd_anomaly)
    assert dec_anomaly.classification == "ANOMALY"
    assert dec_anomaly.anomaly_probability > 0.50


def test_coordinator_arbitration(test_setup):
    """Verify Coordinator Agent synthesizes multi-agent recommendations and produces final action."""
    sat, env, channel, qkd = test_setup
    coordinator = CoordinatorAgent()

    dec = coordinator.step(sat, env, channel, qkd)
    assert dec.final_action.controller_type == "MULTI_AGENT"
    assert 5.0 <= dec.final_action.transmission_power_pct <= 100.0
    assert 0.05 <= dec.final_action.photon_rate_norm <= 1.0
    assert 0.10 <= dec.final_action.beam_divergence_norm <= 1.0


def test_api_control_and_ai_endpoints():
    """Verify API endpoints for control and multi-agent systems."""
    # 1. GET /api/control/current
    res_ctrl = client.get("/api/control/current")
    assert res_ctrl.status_code == 200
    assert "transmission_power_pct" in res_ctrl.json()

    # 2. POST /api/control/mode
    res_mode = client.post("/api/control/mode", json={"controller_type": "MULTI_AGENT"})
    assert res_mode.status_code == 200
    assert res_mode.json()["active_controller"] == "MULTI_AGENT"

    # 3. GET /api/ai/multi_agent
    res_ai = client.get("/api/ai/multi_agent")
    assert res_ai.status_code == 200
    data = res_ai.json()
    assert "weather_agent" in data
    assert "communication_agent" in data
    assert "security_agent" in data
    assert "final_action" in data
