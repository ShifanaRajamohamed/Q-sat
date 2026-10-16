"""
exp12_ai_adaptation.py — Experiment 12: AI Actuator Adaptation Under Environmental Disturbance

Analyzes real-time continuous adaptation of the three physical ground station actuators:
1. Transmission Power (% / mW)
2. Photon Emission Rate (normalized / MHz)
3. Optical Beam Divergence (normalized / mrad)

Against dynamic atmospheric turbulence, cloud attenuation, and orbital elevation dynamics.
Explicitly labeled: SIMULATED ENVIRONMENT.
Produces time-series logs, correlation statistics, and multi-panel publication figures.
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
from ai.agents.coordinator import CoordinatorAgent
from experiments.plot_utils import create_figure, save_figure, PALETTE

OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "ai_adaptation"


def run_adaptation_experiment(duration_s: int = 300, seed: int = 42) -> pd.DataFrame:
    print("=" * 70)
    print("  EXPERIMENT 12: REAL-TIME AI ACTUATOR ADAPTATION")
    print("  Data Provenance: SIMULATED ENVIRONMENT")
    print(f"  Duration: {duration_s}s | Seed: {seed} | Agent: Hierarchical Coordinator")
    print("=" * 70)

    np.random.seed(seed)
    gs = GroundStationConfig(station_id="GS-RESEARCH-01", latitude=10.7905, longitude=78.7047, altitude_m=80.0)
    orbit = OrbitalModel(ground_station=gs)
    channel_model = OpticalChannelModel()
    bb84 = BB84Model()
    coordinator = CoordinatorAgent()

    records = []
    dt = 1.0

    # Initial state
    sat_prev = orbit.propagate(0.0)
    env_prev = EnvironmentData(
        timestamp=0.0,
        temperature=25.0,
        humidity=50.0,
        ambient_light=400.0,
        vibration=0.01,
        cloud_factor=0.05,
        turbulence=0.10,
        data_source="SIMULATION"
    )
    chan_prev = channel_model.calculate_link_state(sat_prev, env_prev, 50.0, 0.70, 0.25)
    qkd_prev = bb84.evaluate(chan_prev, env_prev, 0.0, 0.0)

    for t in np.arange(0.0, duration_s + dt, dt):
        sat = orbit.propagate(t)

        # Non-stationary atmospheric disturbance profile:
        # Step change in cloud cover around t=120s to 180s, high turbulence spike around t=200s
        cloud = 0.08 + 0.10 * np.sin(0.02 * t) ** 2
        if 110 <= t <= 170:
            cloud += 0.45 * np.sin(np.pi * (t - 110) / 60)  # Dense localized cloud plume
        cloud = float(np.clip(cloud, 0.0, 0.95))

        turb = 0.12 + 0.15 * np.sin(0.015 * t) ** 2
        if 180 <= t <= 230:
            turb += 0.35 * np.sin(np.pi * (t - 180) / 50)  # Thermal boundary layer updraft
        turb = float(np.clip(turb, 0.0, 0.90))

        vib = 0.010 + 0.005 * np.sin(0.05 * t) ** 2
        if 70 <= t <= 95:
            vib += 0.035  # Mechanical mount jitter
        vib = float(np.clip(vib, 0.005, 0.080))

        env = EnvironmentData(
            timestamp=t,
            temperature=25.0,
            humidity=60.0,
            ambient_light=450.0,
            vibration=vib,
            cloud_factor=cloud,
            turbulence=turb,
            data_source="SIMULATION"
        )

        dec = coordinator.step(sat, env, chan_prev, qkd_prev)
        action = dec.final_action

        chan = channel_model.calculate_link_state(
            sat, env,
            action.transmission_power_pct,
            action.photon_rate_norm,
            action.beam_divergence_norm
        )
        qkd = bb84.evaluate(chan, env, t, 0.0)

        chan_prev = chan
        qkd_prev = qkd

        records.append({
            "timestamp_s": t,
            "elevation_deg": sat.elevation_deg,
            "cloud_factor": env.cloud_factor,
            "turbulence": env.turbulence,
            "vibration": env.vibration,
            "total_loss_db": chan.total_loss_db,
            "actuator_power_pct": action.transmission_power_pct,
            "actuator_photon_rate": action.photon_rate_norm,
            "actuator_beam_divergence": action.beam_divergence_norm,
            "conflict_detected": dec.conflict_detected,
            "qber_pct": qkd.qber * 100.0,
            "skr_kbps": qkd.secret_key_rate / 1e3,
            "distillable": qkd.is_key_distillation_possible
        })

    df = pd.DataFrame(records)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_DIR / "adaptation_timeseries.csv", index=False)
    print(f"  [SAVED CSV] {OUTPUT_DIR / 'adaptation_timeseries.csv'}")

    summary = pd.DataFrame([{
        "Mean Power (%)": round(df["actuator_power_pct"].mean(), 2),
        "Max Power (%)": round(df["actuator_power_pct"].max(), 2),
        "Mean Divergence": round(df["actuator_beam_divergence"].mean(), 4),
        "Mean Photon Rate": round(df["actuator_photon_rate"].mean(), 4),
        "Conflicts Resolved": int(df["conflict_detected"].sum()),
        "Uptime (%)": round(df["distillable"].mean() * 100.0, 1),
        "Mean SKR (kbps)": round(df["skr_kbps"].mean(), 4)
    }])
    summary.to_csv(OUTPUT_DIR / "adaptation_summary.csv", index=False)
    print(f"  [SAVED CSV] {OUTPUT_DIR / 'adaptation_summary.csv'}")

    return df


def plot_adaptation_figures(df: pd.DataFrame):
    t = df["timestamp_s"]

    # 1. Stacked 3-panel showing Actuator Dynamic Traces vs Disturbance
    fig1, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)

    # Panel 1: Environmental disturbance
    ax1 = axes[0]
    ax1.plot(t, df["cloud_factor"], label="Cloud Coverage", color="#64748b", lw=2.0)
    ax1.plot(t, df["turbulence"], label="Turbulence Index", color="#f59e0b", lw=2.0, linestyle="--")
    ax1.plot(t, df["vibration"] * 10.0, label="Vibration Jitter (x10)", color="#ef4444", lw=1.8, linestyle=":")
    ax1.set_ylabel("Disturbance Index")
    ax1.set_title("SIMULATED ENVIRONMENT: Real-Time Dynamic Atmospheric Disturbance Profile", fontsize=12, weight="bold")
    ax1.legend(loc="upper right", framealpha=0.9)
    ax1.grid(True, alpha=0.3)

    # Panel 2: Three Actuator Responses
    ax2 = axes[1]
    ax2.plot(t, df["actuator_power_pct"], label="Laser Power (%)", color="#0284c7", lw=2.4)
    ax2.set_ylabel("Power (%)", color="#0284c7")
    ax2.tick_params(axis="y", labelcolor="#0284c7")

    ax2_r = ax2.twinx()
    ax2_r.plot(t, df["actuator_beam_divergence"], label="Beam Divergence (norm)", color="#7c3aed", lw=2.0, linestyle="-.")
    ax2_r.plot(t, df["actuator_photon_rate"], label="Photon Rate (norm)", color="#059669", lw=2.0, linestyle="--")
    ax2_r.set_ylabel("Norm [0, 1]", color="#059669")
    ax2_r.tick_params(axis="y", labelcolor="#059669")
    ax2.set_title("Actuator Dynamic Adjustments (Power, Divergence, Rate)", fontsize=11, weight="bold")
    ax2.grid(True, alpha=0.3)

    # Panel 3: Resulting QKD Performance (SKR and QBER)
    ax3 = axes[2]
    ax3.plot(t, df["skr_kbps"], label="Secret Key Rate (kbps)", color="#059669", lw=2.4)
    ax3.set_ylabel("SKR (kbps)", color="#059669")
    ax3.tick_params(axis="y", labelcolor="#059669")
    ax3.set_xlabel("Elapsed Time (seconds)")

    ax3_q = ax3.twinx()
    ax3_q.plot(t, df["qber_pct"], label="QBER (%)", color="#dc2626", lw=1.8, linestyle="--")
    ax3_q.axhline(11.0, color="#991b1b", lw=1.5, linestyle=":", label="11% Cutoff")
    ax3_q.set_ylabel("QBER (%)", color="#dc2626")
    ax3_q.tick_params(axis="y", labelcolor="#dc2626")
    ax3.set_title("Resulting Quantum Optical Link Performance", fontsize=11, weight="bold")
    ax3.grid(True, alpha=0.3)

    save_figure(fig1, OUTPUT_DIR / "actuator_dynamic_traces.png")

    # 2. Phase-space correlation: Power vs Elevation and Divergence vs Turbulence
    fig2, (ax_a, ax_b) = create_figure(nrows=1, ncols=2, figsize=(13, 5))

    sc1 = ax_a.scatter(df["elevation_deg"], df["actuator_power_pct"], c=df["cloud_factor"], cmap="viridis", s=40, alpha=0.85)
    ax_a.set_title("Transmission Power vs Elevation Angle", fontsize=11, weight="bold")
    ax_a.set_xlabel("Elevation Angle (deg)")
    ax_a.set_ylabel("Transmission Power (%)")
    cb1 = fig2.colorbar(sc1, ax=ax_a)
    cb1.set_label("Cloud Coverage", rotation=270, labelpad=15)
    ax_a.grid(True, alpha=0.3)

    sc2 = ax_b.scatter(df["turbulence"], df["actuator_beam_divergence"], c=df["vibration"], cmap="plasma", s=40, alpha=0.85)
    ax_b.set_title("Beam Divergence vs Turbulence & Vibration", fontsize=11, weight="bold")
    ax_b.set_xlabel("Turbulence Index (0-1)")
    ax_b.set_ylabel("Beam Divergence (norm)")
    cb2 = fig2.colorbar(sc2, ax=ax_b)
    cb2.set_label("Platform Vibration (g)", rotation=270, labelpad=15)
    ax_b.grid(True, alpha=0.3)

    fig2.suptitle("SIMULATED ENVIRONMENT: AI Multi-Variable Actuator Response Topology", fontsize=13, weight="bold", y=1.02)
    save_figure(fig2, OUTPUT_DIR / "actuator_phase_plots.png")


if __name__ == "__main__":
    df = run_adaptation_experiment(duration_s=300, seed=42)
    plot_adaptation_figures(df)
    print("  [SUCCESS] Experiment 12 execution completed.")
