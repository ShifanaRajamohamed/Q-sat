"""Pydantic models for Optical Channel Link Budget and BB84 QKD Metrics."""

from typing import Dict, Literal, Optional
from pydantic import BaseModel, Field


class OpticalChannelState(BaseModel):
    """Link budget and physical transmission metrics of the optical channel."""
    total_loss_db: float = Field(..., ge=0.0, description="Total optical path loss in dB")
    transmittance: float = Field(..., ge=0.0, le=1.0, description="End-to-end channel transmittance [0.0 to 1.0]")
    fspl_loss_db: float = Field(..., ge=0.0, description="Geometric free-space path loss in dB")
    atmospheric_loss_db: float = Field(..., ge=0.0, description="Atmospheric absorption, scattering and cloud loss in dB")
    pointing_loss_db: float = Field(..., ge=0.0, description="Beam mispointing and platform vibration jitter loss in dB")
    scintillation_loss_db: float = Field(..., ge=0.0, description="Turbulence scintillation fading loss in dB")
    received_photon_rate: float = Field(..., ge=0.0, description="Effective received photon rate (photons/second or MHz)")
    background_noise_rate: float = Field(..., ge=0.0, description="Background optical stray photon rate (counts/second)")
    snr_db: float = Field(..., description="Optical Signal-to-Noise Ratio (dB)")
    beam_spot_radius_m: float = Field(..., ge=0.0, description="Diffraction & divergence beam spot radius at receiver (meters)")


class QBERDecomposition(BaseModel):
    """Root-cause decomposition of Quantum Bit Error Rate (QBER).
    
    QBER = base_error + atmospheric_noise + background_light_noise + pointing_error + detector_noise + anomaly_component
    """
    base_error: float = Field(..., ge=0.0, le=0.5, description="Intrinsic optical alignment and polarization baseline error")
    atmospheric_noise: float = Field(..., ge=0.0, le=0.5, description="Error induced by atmospheric scattering and phase jitter")
    background_light_noise: float = Field(..., ge=0.0, le=0.5, description="Error induced by ambient stray photons")
    pointing_error: float = Field(..., ge=0.0, le=0.5, description="Error caused by mount vibration and beam wander")
    detector_noise: float = Field(..., ge=0.0, le=0.5, description="Error contributed by detector dark counts")
    security_anomaly_component: float = Field(0.0, ge=0.0, le=0.5, description="Anomalous error component (e.g. simulated eavesdropping/fault)")
    total_qber: float = Field(..., ge=0.0, le=0.5, description="Composite QBER bounded strictly in [0.0, 0.5]")


class QKDMetrics(BaseModel):
    """BB84 Analytical Quantum Key Distribution performance metrics."""
    timestamp: float = Field(..., description="Simulation epoch timestamp in seconds")
    transmitted_photon_rate: float = Field(..., ge=0.0, description="Transmitter photon emission rate (photons/sec)")
    received_photon_rate: float = Field(..., ge=0.0, description="Receiver single-photon detection rate (photons/sec)")
    raw_key_rate: float = Field(..., ge=0.0, description="Raw key generation rate before basis reconciliation (bps)")
    sifted_key_rate: float = Field(..., ge=0.0, description="Sifted key generation rate after basis matching (bps)")
    qber: float = Field(..., ge=0.0, le=0.5, description="Quantum Bit Error Rate (0.0 to 0.50)")
    secret_key_rate: float = Field(..., ge=0.0, description="Asymptotic secret key rate after error correction & privacy amplification (bps)")
    qber_decomposition: QBERDecomposition = Field(..., description="Multi-factor attribution of QBER")
    channel_loss_db: float = Field(..., ge=0.0, description="Optical channel loss in dB")
    channel_transmittance: float = Field(..., ge=0.0, le=1.0, description="Optical channel transmittance")
    is_key_distillation_possible: bool = Field(..., description="True if QBER is below BB84 threshold (~11%) and SKR > 0")
    status_label: Literal["OPTIMAL", "DEGRADED", "CRITICAL_QBER", "LINK_DOWN"] = Field(
        "OPTIMAL", description="High-level link health status"
    )
