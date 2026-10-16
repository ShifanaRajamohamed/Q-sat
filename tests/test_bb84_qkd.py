"""Unit and integration tests for Phase 5: BB84-Inspired Analytical QKD Model."""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.environment import EnvironmentData
from backend.app.models.qkd import OpticalChannelState
from qkd.bb84_model import BB84Model
from qkd.key_rate import calculate_raw_key_rate, calculate_sifted_key_rate
from qkd.qber import calculate_qber
from qkd.secret_key_rate import binary_entropy, calculate_secret_key_rate

client = TestClient(app)


def test_binary_entropy():
    """Verify binary Shannon entropy mathematical properties."""
    assert binary_entropy(0.0) == 0.0
    assert binary_entropy(1.0) == 0.0
    assert binary_entropy(0.5) == 1.0
    assert 0.0 < binary_entropy(0.05) < 0.30


def test_secret_key_rate_security_cutoff():
    """Verify asymptotic SKR drops to zero at and above the 11% BB84 security limit."""
    # Under 5% QBER -> positive secret key rate
    skr_good, r_good, sec_good = calculate_secret_key_rate(sifted_key_rate=10000.0, qber=0.03)
    assert skr_good > 0.0
    assert sec_good is True

    # At 11% QBER -> security limit reached, SKR = 0
    skr_cutoff, r_cutoff, sec_cutoff = calculate_secret_key_rate(sifted_key_rate=10000.0, qber=0.110)
    assert skr_cutoff == 0.0
    assert sec_cutoff is False

    # Above 11% QBER -> SKR must be strictly 0, never negative
    skr_high, r_high, sec_high = calculate_secret_key_rate(sifted_key_rate=10000.0, qber=0.150)
    assert skr_high == 0.0
    assert sec_high is False


def test_qber_attribution():
    """Verify QBER components sum up and stay within [0.0, 0.50]."""
    channel = OpticalChannelState(
        total_loss_db=22.0, transmittance=0.0063, fspl_loss_db=15.0, atmospheric_loss_db=4.0,
        pointing_loss_db=2.0, scintillation_loss_db=1.0, received_photon_rate=50000.0,
        background_noise_rate=500.0, snr_db=20.0, beam_spot_radius_m=12.0
    )
    env = EnvironmentData(
        timestamp=0.0, temperature=25.0, humidity=50.0, ambient_light=500.0,
        vibration=0.02, cloud_factor=0.05, turbulence=0.10, data_source="SIMULATION"
    )

    decomp = calculate_qber(channel, env, anomaly_component=0.0)
    assert 0.0 < decomp.total_qber < 0.10
    assert decomp.base_error == pytest.approx(0.01)
    assert decomp.total_qber <= 0.50


def test_api_qkd_current():
    """Verify GET /api/qkd/current returns valid analytical QKD metrics."""
    response = client.get("/api/qkd/current")
    assert response.status_code == 200
    data = response.json()

    assert "qber" in data
    assert "secret_key_rate" in data
    assert "raw_key_rate" in data
    assert "sifted_key_rate" in data
    assert "qber_decomposition" in data
    assert data["secret_key_rate"] >= 0.0
    assert 0.0 <= data["qber"] <= 0.50


def test_api_qkd_anomaly_injection():
    """Verify injecting and clearing security anomaly via API."""
    # Inject 8% error anomaly
    inject_res = client.post("/api/qkd/anomaly", json={"qber_offset": 0.08})
    assert inject_res.status_code == 200

    # Query metrics
    metrics_res = client.get("/api/qkd/current")
    assert metrics_res.status_code == 200
    metrics = metrics_res.json()
    assert metrics["qber_decomposition"]["security_anomaly_component"] == pytest.approx(0.08)

    # Clear anomaly
    clear_res = client.delete("/api/qkd/anomaly")
    assert clear_res.status_code == 200
