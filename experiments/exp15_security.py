"""
exp15_security.py — Experiment 15: Security Anomaly Detection & QBER Attribution

Evaluates the Security Agent's multi-factor attribution algorithm:
1. Benign Severe Atmospheric Disturbance (High QBER, but 100% physically explained -> Normal/Degraded)
2. Malicious Quantum Eavesdropping (Moderate physical disturbance, but unexplained QBER -> Anomaly Alert)
3. Parametric sweep of injected anomaly component (0.0% to 10.0%) to assess detection sensitivity.

Explicitly labeled: SIMULATED ENVIRONMENT.
Produces discrimination datasets and publication validation figures.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from digital_twin.orbital_model import OrbitalModel
from digital_twin.optical_channel import OpticalChannelModel
from qkd.bb84_model import BB84Model
from backend.app.models.satellite import GroundStationConfig
from backend.app.models.environment import EnvironmentData
from ai.agents.security_agent import SecurityAgent
from experiments.plot_utils import create_figure, save_figure, PALETTE

OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "security"


def run_security_experiments() -> tuple[pd.DataFrame, pd.DataFrame]:
    print("=" * 70)
    print("  EXPERIMENT 15: SECURITY ANOMALY DETECTION & QBER ATTRIBUTION")
    print("  Data Provenance: SIMULATED ENVIRONMENT")
    print("=" * 70)

    gs = GroundStationConfig(latitude=10.7905, longitude=78.7047, altitude_m=80.0)
    orbit = OrbitalModel(ground_station=gs)
    channel_model = OpticalChannelModel()
    bb84 = BB84Model()

    # Part A: Parametric sweep of injected anomaly from 0.0% to 10.0%
    print("  Running Parametric Anomaly Sweep (0% to 10%)...")
    sweep_records = []
    sat = orbit.propagate(150.0)  # Mid-pass zenith (~70 deg elevation)
    env_clear = EnvironmentData(
        timestamp=150.0,
        temperature=25.0,
        humidity=45.0,
        ambient_light=500.0,
        vibration=0.010,
        cloud_factor=0.05,
        turbulence=0.08,
        data_source="SIMULATION"
    )
    chan = channel_model.calculate_link_state(sat, env_clear, 50.0, 0.70, 0.25)

    for anomaly_pct in np.linspace(0.0, 10.0, 21):
        anomaly_val = anomaly_pct / 100.0
        sec_agent = SecurityAgent()

        qkd = bb84.evaluate(chan, env_clear, 150.0, anomaly_component=anomaly_val)
        sec_dec = sec_agent.analyze(env_clear, chan, qkd)

        decomp = qkd.qber_decomposition
        phys_explained = (
            decomp.base_error + decomp.atmospheric_noise +
            decomp.background_light_noise + decomp.pointing_error +
            decomp.detector_noise
        )

        sweep_records.append({
            "injected_anomaly_pct": round(anomaly_pct, 2),
            "observed_total_qber_pct": round(qkd.qber * 100.0, 3),
            "modeled_physical_qber_pct": round(phys_explained * 100.0, 3),
            "unexplained_error_pct": round(max(0.0, qkd.qber - phys_explained) * 100.0, 3),
            "anomaly_probability": round(sec_dec.anomaly_probability, 4),
            "classification": sec_dec.classification,
            "secret_key_rate_kbps": round(qkd.secret_key_rate / 1e3, 4),
            "primary_error_driver": sec_dec.primary_error_driver
        })

    sweep_df = pd.DataFrame(sweep_records)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sweep_df.to_csv(OUTPUT_DIR / "security_sweep_metrics.csv", index=False)
    print(f"  [SAVED CSV] {OUTPUT_DIR / 'security_sweep_metrics.csv'}")

    # Part B: Pass Timeline with benign atmospheric storm vs cyber/physical attack
    print("  Running Timeline Comparison (Benign Storm vs Cyber Attack)...")
    timeline_records = []
    sec_agent_storm = SecurityAgent()
    sec_agent_attack = SecurityAgent()

    for t in np.arange(0.0, 300.0, 2.0):
        sat = orbit.propagate(t)

        # 1. Benign Storm: Heavy clouds, turbulence, vibration (NO anomaly)
        cloud_storm = float(np.clip(0.10 + 0.65 * np.sin(np.pi * t / 300.0) ** 2, 0.0, 0.95))
        turb_storm = float(np.clip(0.10 + 0.50 * np.sin(np.pi * t / 300.0) ** 2, 0.0, 0.90))
        vib_storm = float(np.clip(0.010 + 0.040 * np.sin(np.pi * t / 300.0) ** 2, 0.005, 0.060))
        env_storm = EnvironmentData(
            timestamp=t, temperature=24.0, humidity=80.0, ambient_light=600.0,
            vibration=vib_storm, cloud_factor=cloud_storm, turbulence=turb_storm, data_source="SIMULATION"
        )
        chan_storm = channel_model.calculate_link_state(sat, env_storm, 75.0, 0.80, 0.25)
        qkd_storm = bb84.evaluate(chan_storm, env_storm, t, anomaly_component=0.0)
        dec_storm = sec_agent_storm.analyze(env_storm, chan_storm, qkd_storm)

        # 2. Attack Scenario: Mild weather, but active intercept-resend attack between t=100 and t=200
        env_attack = EnvironmentData(
            timestamp=t, temperature=25.0, humidity=50.0, ambient_light=400.0,
            vibration=0.010, cloud_factor=0.08, turbulence=0.10, data_source="SIMULATION"
        )
        chan_attack = channel_model.calculate_link_state(sat, env_attack, 75.0, 0.80, 0.25)
        attack_injection = 0.045 if (100.0 <= t <= 200.0) else 0.0
        qkd_attack = bb84.evaluate(chan_attack, env_attack, t, anomaly_component=attack_injection)
        dec_attack = sec_agent_attack.analyze(env_attack, chan_attack, qkd_attack)

        timeline_records.append({
            "timestamp_s": t,
            "elevation_deg": sat.elevation_deg,
            # Benign Storm
            "storm_qber_pct": qkd_storm.qber * 100.0,
            "storm_anomaly_prob": dec_storm.anomaly_probability,
            "storm_classification": dec_storm.classification,
            # Cyber Attack
            "attack_qber_pct": qkd_attack.qber * 100.0,
            "attack_anomaly_prob": dec_attack.anomaly_probability,
            "attack_classification": dec_attack.classification,
        })

    timeline_df = pd.DataFrame(timeline_records)
    timeline_df.to_csv(OUTPUT_DIR / "security_discrimination_timeseries.csv", index=False)
    print(f"  [SAVED CSV] {OUTPUT_DIR / 'security_discrimination_timeseries.csv'}")

    return sweep_df, timeline_df


def plot_security_figures(sweep_df: pd.DataFrame, timeline_df: pd.DataFrame):
    # 1. Expected Physical vs Observed Total QBER
    fig1, ax1 = create_figure(
        title="SIMULATED ENVIRONMENT: Expected Physical vs Observed Total QBER",
        xlabel="Injected Unexplained Anomaly Component (%)",
        ylabel="QBER (%)"
    )
    ax1.plot(sweep_df["injected_anomaly_pct"], sweep_df["observed_total_qber_pct"], color=PALETTE["danger"], lw=2.4, marker="o", label="Observed Total QBER")
    ax1.plot(sweep_df["injected_anomaly_pct"], sweep_df["modeled_physical_qber_pct"], color=PALETTE["neutral"], lw=2.0, linestyle="--", label="Model-Predicted Physical QBER")
    ax1.fill_between(
        sweep_df["injected_anomaly_pct"],
        sweep_df["modeled_physical_qber_pct"],
        sweep_df["observed_total_qber_pct"],
        color=PALETTE["danger"],
        alpha=0.20,
        label="Attributed Anomaly Residual"
    )
    ax1.axhline(11.0, color="#991b1b", lw=1.8, linestyle=":", label="BB84 Cutoff (11.0%)")
    ax1.legend(loc="upper left", framealpha=0.9)
    ax1.grid(True, alpha=0.3)
    save_figure(fig1, OUTPUT_DIR / "security_anomaly_vs_qber.png")

    # 2. Anomaly Detection Probability & Classification Boundary
    fig2, ax2 = create_figure(
        title="SIMULATED ENVIRONMENT: Security Anomaly Detection Probability vs Attack Strength",
        xlabel="Injected Unexplained Anomaly Component (%)",
        ylabel="Anomaly Probability Score"
    )
    ax2.plot(sweep_df["injected_anomaly_pct"], sweep_df["anomaly_probability"], color="#7c3aed", lw=2.4, marker="s", label="Assessed Anomaly Probability")
    ax2.axhline(0.50, color="#dc2626", lw=1.8, linestyle="--", label="Anomaly Classification Threshold (0.50)")
    ax2.axvline(3.5, color="#f59e0b", lw=1.5, linestyle=":", label="Detection Sensitivity Floor (3.5%)")
    ax2.set_ylim(-0.05, 1.05)
    ax2.legend(loc="lower right", framealpha=0.9)
    ax2.grid(True, alpha=0.3)
    save_figure(fig2, OUTPUT_DIR / "security_detection_probability.png")

    # 3. Discrimination Timeline: Benign Atmospheric Storm vs Malicious Attack
    fig3, (ax_q, ax_prob) = create_figure(nrows=2, ncols=1, figsize=(11, 8))
    t = timeline_df["timestamp_s"]

    # QBER subplot
    ax_q.plot(t, timeline_df["storm_qber_pct"], label="Severe Benign Storm QBER", color="#0284c7", lw=2.2)
    ax_q.plot(t, timeline_df["attack_qber_pct"], label="Malicious Attack QBER (100-200s)", color="#dc2626", lw=2.2, linestyle="--")
    ax_q.axhline(11.0, color="black", lw=1.5, linestyle=":", label="Security Cutoff")
    ax_q.set_ylabel("Total QBER (%)")
    ax_q.set_title("SIMULATED ENVIRONMENT: Discrimination — Benign Environmental Storm vs Cyber-Physical Attack", fontsize=12, weight="bold")
    ax_q.legend(loc="upper right", framealpha=0.9)
    ax_q.grid(True, alpha=0.3)

    # Anomaly probability score subplot
    ax_prob.plot(t, timeline_df["storm_anomaly_prob"], label="Storm Anomaly Prob (Correctly Low)", color="#0284c7", lw=2.0)
    ax_prob.plot(t, timeline_df["attack_anomaly_prob"], label="Attack Anomaly Prob (Correctly High)", color="#dc2626", lw=2.4)
    ax_prob.axhline(0.50, color="#991b1b", lw=1.5, linestyle="--", label="Alert Threshold")
    ax_prob.fill_between(t, 0.50, 1.0, color="#fee2e2", alpha=0.4)
    ax_prob.set_ylabel("Anomaly Probability")
    ax_prob.set_xlabel("Elapsed Time (seconds)")
    ax_prob.set_ylim(-0.05, 1.05)
    ax_prob.legend(loc="upper right", framealpha=0.9)
    ax_prob.grid(True, alpha=0.3)

    save_figure(fig3, OUTPUT_DIR / "security_storm_vs_attack.png")


if __name__ == "__main__":
    sweep_df, timeline_df = run_security_experiments()
    plot_security_figures(sweep_df, timeline_df)
    print("  [SUCCESS] Experiment 15 execution completed.")
