"""
exp14_digital_twin.py — Experiment 14: Digital Twin State Tracking & Physics Synchronization

Executes full-pass state propagation through the central DigitalTwin orchestrator,
demonstrating continuous synchronization between orbital mechanics, physical environmental
telemetry (Ornstein-Uhlenbeck dynamics), and multi-factor optical channel link budgets.

Explicitly labeled: SIMULATED ENVIRONMENT.
Produces synchronized telemetry datasets and multi-panel physics validation figures.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from backend.app.models.environment import ScenarioType
from backend.app.models.satellite import GroundStationConfig
from digital_twin.digital_twin import DigitalTwin
from digital_twin.simulation_environment_provider import SimulationEnvironmentProvider
from qkd.bb84_model import BB84Model
from experiments.plot_utils import create_figure, save_figure, PALETTE

OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "digital_twin"


def run_digital_twin_experiment(duration_s: int = 300, seed: int = 42) -> pd.DataFrame:
    print("=" * 70)
    print("  EXPERIMENT 14: DIGITAL TWIN ORCHESTRATION & STATE TRACKING")
    print("  Data Provenance: SIMULATED ENVIRONMENT")
    print(f"  Duration: {duration_s}s | Seed: {seed} | Scenario: COMBINED_DEGRADATION")
    print("=" * 70)

    gs = GroundStationConfig(name="Trichy OGS", latitude=10.7905, longitude=78.7047, altitude_m=80.0)
    env_provider = SimulationEnvironmentProvider(scenario=ScenarioType.COMBINED_DEGRADATION, seed=seed)
    twin = DigitalTwin(environment_provider=env_provider, ground_station=gs, satellite_altitude_km=500.0)
    bb84 = BB84Model()

    records = []
    dt = 1.0

    # Reset
    sat, env, chan = twin.reset(seed=seed)

    for step_idx in range(duration_s):
        # Step twin with dynamic adaptive inputs
        sat, env, chan = twin.step(
            dt=dt,
            transmission_power_pct=75.0,
            photon_rate_norm=0.80,
            beam_divergence_norm=0.25
        )

        qkd = bb84.evaluate(chan, env, timestamp=twin.current_time, anomaly_component=0.0)

        records.append({
            "timestamp_s": twin.current_time,
            # Satellite state
            "elevation_deg": sat.elevation_deg,
            "azimuth_deg": sat.azimuth_deg,
            "slant_range_km": sat.slant_range_km,
            "is_visible": sat.is_visible,
            "orbital_velocity_km_s": sat.orbital_velocity_km_s,
            # Environmental Telemetry
            "temperature_c": env.temperature,
            "humidity_pct": env.humidity,
            "ambient_light_lux": env.ambient_light,
            "vibration_g": env.vibration,
            "cloud_factor": env.cloud_factor,
            "turbulence": env.turbulence,
            # Optical Channel Physics
            "fspl_loss_db": chan.fspl_loss_db,
            "atmospheric_loss_db": chan.atmospheric_loss_db,
            "pointing_loss_db": chan.pointing_loss_db,
            "scintillation_loss_db": chan.scintillation_loss_db,
            "total_loss_db": chan.total_loss_db,
            "transmittance": chan.transmittance,
            "received_photon_rate": chan.received_photon_rate,
            "snr_db": chan.snr_db,
            "beam_spot_radius_m": chan.beam_spot_radius_m,
            # Quantum Performance
            "qber_pct": qkd.qber * 100.0,
            "secret_key_rate_kbps": qkd.secret_key_rate / 1e3,
            "is_distillable": qkd.is_key_distillation_possible
        })

    df = pd.DataFrame(records)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_DIR / "digital_twin_telemetry.csv", index=False)
    print(f"  [SAVED CSV] {OUTPUT_DIR / 'digital_twin_telemetry.csv'}")

    summary = pd.DataFrame([{
        "Total Steps": len(df),
        "Max Elevation (deg)": round(df["elevation_deg"].max(), 2),
        "Min Slant Range (km)": round(df["slant_range_km"].min(), 1),
        "Mean Total Loss (dB)": round(df["total_loss_db"].mean(), 2),
        "Mean QBER (%)": round(df["qber_pct"].mean(), 2),
        "Mean SKR (kbps)": round(df["secret_key_rate_kbps"].mean(), 4),
        "Total Key Produced (kbits)": round(df["secret_key_rate_kbps"].sum() * dt, 2),
        "Link Uptime (%)": round(df["is_distillable"].mean() * 100.0, 1)
    }])
    summary.to_csv(OUTPUT_DIR / "digital_twin_summary.csv", index=False)
    print(f"  [SAVED CSV] {OUTPUT_DIR / 'digital_twin_summary.csv'}")

    return df


def plot_digital_twin_figures(df: pd.DataFrame):
    t = df["timestamp_s"]

    # 1. Multi-panel state vector tracking
    fig1, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

    # Subplot 1: Orbital Geometry (Elevation & Slant Range)
    ax1 = axes[0]
    ax1.plot(t, df["elevation_deg"], color="#7c3aed", lw=2.2, label="Elevation (°)")
    ax1.set_ylabel("Elevation (°)", color="#7c3aed")
    ax1.tick_params(axis="y", labelcolor="#7c3aed")
    ax1.set_title("SIMULATED ENVIRONMENT: Digital Twin Real-Time State Vector Synchronization", fontsize=12, weight="bold")

    ax1_r = ax1.twinx()
    ax1_r.plot(t, df["slant_range_km"], color="#64748b", lw=2.0, linestyle="--", label="Slant Range (km)")
    ax1_r.set_ylabel("Slant Range (km)", color="#64748b")
    ax1_r.tick_params(axis="y", labelcolor="#64748b")
    ax1.grid(True, alpha=0.3)

    # Subplot 2: Environmental Stochastic Telemetry
    ax2 = axes[1]
    ax2.plot(t, df["cloud_factor"], color="#0284c7", lw=2.0, label="Cloud Factor (0-1)")
    ax2.plot(t, df["turbulence"], color="#f59e0b", lw=1.8, linestyle="--", label="Atmospheric Turbulence (0-1)")
    ax2.plot(t, df["vibration_g"] * 20.0, color="#ef4444", lw=1.5, linestyle=":", label="Mount Vibration (x20 g)")
    ax2.set_ylabel("Normalized Telemetry")
    ax2.legend(loc="upper right", framealpha=0.9)
    ax2.grid(True, alpha=0.3)

    # Subplot 3: Link Transmittance & Secret Key Rate
    ax3 = axes[2]
    ax3.plot(t, df["total_loss_db"], color="#d97706", lw=2.2, label="Total Channel Path Loss (dB)")
    ax3.set_ylabel("Total Loss (dB)", color="#d97706")
    ax3.tick_params(axis="y", labelcolor="#d97706")
    ax3.set_xlabel("Elapsed Time (seconds)")

    ax3_s = ax3.twinx()
    ax3_s.plot(t, df["secret_key_rate_kbps"], color="#059669", lw=2.4, label="Secret Key Rate (kbps)")
    ax3_s.set_ylabel("SKR (kbps)", color="#059669")
    ax3_s.tick_params(axis="y", labelcolor="#059669")
    ax3.grid(True, alpha=0.3)

    save_figure(fig1, OUTPUT_DIR / "digital_twin_state_timeline.png")

    # 2. Optical Link Budget Loss Decomposition (Stacked Area)
    fig2, ax = create_figure(
        title="SIMULATED ENVIRONMENT: Optical Link Budget Decomposition Across Pass",
        xlabel="Elapsed Time (seconds)",
        ylabel="Loss Contribution (dB)"
    )
    ax.stackplot(
        t,
        df["fspl_loss_db"],
        df["atmospheric_loss_db"],
        df["pointing_loss_db"],
        df["scintillation_loss_db"],
        labels=["Geometric FSPL", "Atmospheric & Cloud", "Pointing Misalignment", "Scintillation Fading"],
        colors=["#0284c7", "#f59e0b", "#8b5cf6", "#ef4444"],
        alpha=0.85
    )
    ax.plot(t, df["total_loss_db"], color="black", lw=2.0, linestyle="--", label="Total Channel Loss")
    ax.legend(loc="upper right", framealpha=0.9)
    ax.grid(True, alpha=0.3)
    save_figure(fig2, OUTPUT_DIR / "digital_twin_optical_breakdown.png")


if __name__ == "__main__":
    df = run_digital_twin_experiment(duration_s=300, seed=42)
    plot_digital_twin_figures(df)
    print("  [SUCCESS] Experiment 14 execution completed.")
