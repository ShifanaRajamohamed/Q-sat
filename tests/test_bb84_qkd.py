"""Unit and integration tests for Phase 5: BB84-Inspired Analytical QKD Model."""

import pytest
from backend.app.models.environment import EnvironmentData
from backend.app.models.qkd import OpticalChannelState
from backend.app.services.qkd_service import qkd_service
from qkd.bb84_model import BB84Model
from qkd.key_rate import calculate_raw_key_rate, calculate_sifted_key_rate
from qkd.qber import calculate_qber
from qkd.secret_key_rate import binary_entropy, calculate_secret_key_rate


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


def test_qkd_service_current():
    """Verify QKD service returns valid analytical QKD metrics."""
    metrics = qkd_service.evaluate_current()

    assert metrics.qber is not None
    assert metrics.secret_key_rate is not None
    assert metrics.raw_key_rate is not None
    assert metrics.sifted_key_rate is not None
    assert metrics.qber_decomposition is not None
    assert metrics.secret_key_rate >= 0.0
    assert 0.0 <= metrics.qber <= 0.50


def test_qkd_service_anomaly_injection():
    """Verify injecting and clearing security anomaly via QKD service."""
    # Inject 8% error anomaly
    qkd_service.inject_anomaly(0.08)
    metrics = qkd_service.evaluate_current()
    assert metrics.qber_decomposition.security_anomaly_component == pytest.approx(0.08)

    # Clear anomaly
    qkd_service.clear_anomaly()
    metrics_cleared = qkd_service.evaluate_current()
    assert metrics_cleared.qber_decomposition.security_anomaly_component == pytest.approx(0.0)
