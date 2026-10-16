"""
exp08_dynamic_weather.py — Experiment 8: Dynamic Weather Transition Scenario

Evaluates continuous QKD link adaptation across dynamic atmospheric transitions
during a single orbital pass:
  CLEAR -> MODERATE -> SEVERE -> MODERATE -> CLEAR

Explicitly labeled: SIMULATED ENVIRONMENT.
Generates comprehensive time-series dataset and multi-panel publication figures.
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
from experiments.plot_utils import create_figure, save_figure, PALETTE

OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "dynamic_weather"


def get_dynamic_environment(t: float, total_duration: float = 300.0) -> tuple[EnvironmentData, str]:
    """
    Interpolate realistic environmental parameters across 5 phases:
      Phase 1 [0 - 60s]: Clear Sky
      Phase 2 [60 - 110s]: Transition Clear -> Moderate Haze
      Phase 3 [110 - 180s]: Severe Storm & Cloud Intrusion
      Phase 4 [180 - 240s]: Recovery Severe -> Moderate
      Phase 5 [240 - 300s]: Clear Sky Return
    """
    if t < 60.0:
        # Phase 1: Clear
        regime = "CLEAR"
        cloud = 0.02 + 0.01 * np.sin(0.1 * t)
        turb = 0.05 + 0.01 * np.cos(0.05 * t)
        hum = 45.0 + 2.0 * np.sin(0.08 * t)
        temp = 24.0
        lux = 300.0
        vib = 0.008
    elif t < 110.0:
        # Phase 2: Moderate transition
        frac = (t - 60.0) / 50.0
        regime = "TRANSITION_MOD"
        cloud = 0.02 + frac * (0.35 - 0.02)
        turb = 0.05 + frac * (0.30 - 0.05)
        hum = 45.0 + frac * (80.0 - 45.0)
        temp = 24.0 + frac * 3.0
        lux = 300.0 + frac * 300.0
        vib = 0.008 + frac * 0.008
    elif t < 190.0:
        # Phase 3: Severe storm
        frac = min(1.0, (t - 110.0) / 40.0)
        regime = "SEVERE"
        cloud = 0.35 + frac * (0.88 - 0.35)
        turb = 0.30 + frac * (0.65 - 0.30)
        hum = 80.0 + frac * (96.0 - 80.0)
        temp = 27.0 - frac * 6.0
        lux = 600.0 + frac * 900.0
        vib = 0.016 + frac * 0.025
    elif t < 250.0:
        # Phase 4: Clearing
        frac = (t - 190.0) / 60.0
        regime = "TRANSITION_CLEAR"
        cloud = 0.88 - frac * (0.88 - 0.15)
        turb = 0.65 - frac * (0.65 - 0.12)
        hum = 96.0 - frac * (96.0 - 55.0)
        temp = 21.0 + frac * 3.5
        lux = 1500.0 - frac * 1000.0
        vib = 0.041 - frac * 0.030
    else:
        # Phase 5: Clear
        regime = "CLEAR"
        cloud = 0.05
        turb = 0.08
        hum = 50.0
        temp = 24.5
        lux = 350.0
        vib = 0.010

    env = EnvironmentData(
        timestamp=t,
        temperature=float(temp),
        humidity=float(hum),
        ambient_light=float(lux),
        vibration=float(vib),
        cloud_factor=float(cloud),
        turbulence=float(turb),
        data_source="SIMULATION"
    )
    return env, regime


def run_dynamic_weather_experiment(duration_sec: int = 300, step_dt: float = 1.0) -> pd.DataFrame:
    print("=" * 70)
    print("  EXPERIMENT 8: DYNAMIC WEATHER TRANSITION SCENARIO")
    print("  Data Provenance: SIMULATED ENVIRONMENT")
    print(f"  Duration: {duration_sec}s | Step: {step_dt}s | Regimes: CLEAR -> MOD -> SEVERE -> CLEAR")
    print("=" * 70)

    gs = GroundStationConfig(station_id="GS-RESEARCH-01", latitude=28.6139, longitude=77.2090, altitude=216.0)
    orbit = OrbitalModel(ground_station=gs)
    channel_model = OpticalChannelModel()
    bb84 = BB84Model()

    records = []
    t = 0.0
    while t <= duration_sec:
        sat = orbit.propagate(t)
        env, regime = get_dynamic_environment(t, total_duration=duration_sec)

        # Baseline static transmission parameters
        channel_state = channel_model.calculate_link_state(
            satellite=sat,
            environment=env,
            transmission_power_pct=50.0,
            photon_rate_norm=0.70,
            beam_divergence_norm=0.25
        )

        qkd = bb84.evaluate(
            channel_state=channel_state,
            environment=env,
            timestamp=t,
            anomaly_component=0.0
        )

        records.append({
            "timestamp_s": t,
            "weather_regime": regime,
            "elevation_deg": sat.elevation_deg,
            "distance_km": sat.slant_range_km,
            "cloud_coverage": env.cloud_factor,
            "turbulence_index": env.turbulence,
            "humidity_pct": env.humidity,
            "total_loss_db": channel_state.total_loss_db,
            "atmospheric_loss_db": channel_state.atmospheric_loss_db,
            "geometric_loss_db": channel_state.fspl_loss_db,
            "pointing_loss_db": channel_state.pointing_loss_db,
            "qber_pct": qkd.qber * 100.0,
            "qber_threshold_exceeded": qkd.qber >= 0.11,
            "raw_key_rate_kbps": qkd.raw_key_rate / 1e3,
            "sifted_key_rate_kbps": qkd.sifted_key_rate / 1e3,
            "secret_key_rate_kbps": qkd.secret_key_rate / 1e3,
            "link_established": qkd.secret_key_rate > 0.0,
        })
        t += step_dt

    df = pd.DataFrame(records)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_DIR / "dynamic_weather_timeseries.csv", index=False)
    print(f"  [SAVED CSV] {OUTPUT_DIR / 'dynamic_weather_timeseries.csv'}")

    # Summary table by regime
    summary = df.groupby("weather_regime").agg(
        duration_s=("timestamp_s", "count"),
        mean_cloud=("cloud_coverage", "mean"),
        mean_loss_db=("total_loss_db", "mean"),
        mean_qber_pct=("qber_pct", "mean"),
        mean_skr_kbps=("secret_key_rate_kbps", "mean"),
        uptime_pct=("link_established", lambda x: float(x.mean() * 100.0))
    ).reset_index()
    summary.to_csv(OUTPUT_DIR / "dynamic_weather_summary.csv", index=False)
    print(f"  [SAVED CSV] {OUTPUT_DIR / 'dynamic_weather_summary.csv'}")

    return df


def plot_dynamic_weather_figures(df: pd.DataFrame):
    # 1. Multi-panel timeline figure: Weather parameters, Loss, QBER, and SKR
    fig, axes = plt.subplots(4, 1, figsize=(11, 10), sharex=True)

    t = df["timestamp_s"]

    # Shaded regime backgrounds
    def shade_regimes(ax):
        ax.axvspan(0, 60, color="#10b981", alpha=0.10, label="Clear Phase" if ax == axes[0] else "")
        ax.axvspan(60, 110, color="#f59e0b", alpha=0.12, label="Haze Transition" if ax == axes[0] else "")
        ax.axvspan(110, 190, color="#ef4444", alpha=0.15, label="Severe Storm" if ax == axes[0] else "")
        ax.axvspan(190, 250, color="#f59e0b", alpha=0.12)
        ax.axvspan(250, df["timestamp_s"].max(), color="#10b981", alpha=0.10)

    # Panel 1: Environmental disturbance (Cloud & Turbulence)
    ax1 = axes[0]
    shade_regimes(ax1)
    ax1.plot(t, df["cloud_coverage"], color="#64748b", lw=2.2, label="Cloud Cover (0-1)")
    ax1.plot(t, df["turbulence_index"], color="#f59e0b", lw=2.0, linestyle="--", label="Turbulence Index (0-1)")
    ax1.set_ylabel("Disturbance Index")
    ax1.set_ylim(-0.05, 1.05)
    ax1.legend(loc="upper right", framealpha=0.9)
    ax1.set_title("SIMULATED ENVIRONMENT: Dynamic Weather Transition Across Pass", fontsize=13, weight="bold")

    # Panel 2: Channel Path Loss
    ax2 = axes[1]
    shade_regimes(ax2)
    ax2.plot(t, df["total_loss_db"], color=PALETTE["loss"], lw=2.4, label="Total Channel Loss (dB)")
    ax2.plot(t, df["atmospheric_loss_db"], color="#9333ea", lw=1.8, linestyle=":", label="Atmospheric Loss (dB)")
    ax2.set_ylabel("Channel Loss (dB)")
    ax2.legend(loc="upper right", framealpha=0.9)

    # Panel 3: QBER and Security Threshold
    ax3 = axes[2]
    shade_regimes(ax3)
    ax3.plot(t, df["qber_pct"], color=PALETTE["qber"], lw=2.2, label="Observed QBER (%)")
    ax3.axhline(11.0, color="#991b1b", lw=1.8, linestyle="--", label="Security Cutoff (11.0%)")
    ax3.set_ylabel("QBER (%)")
    ax3.set_ylim(-1, 55)
    ax3.legend(loc="upper right", framealpha=0.9)

    # Panel 4: Secret Key Rate
    ax4 = axes[3]
    shade_regimes(ax4)
    ax4.plot(t, df["secret_key_rate_kbps"], color=PALETTE["skr"], lw=2.4, label="Secret Key Rate (kbps)")
    ax4.fill_between(t, 0, df["secret_key_rate_kbps"], color=PALETTE["skr"], alpha=0.25)
    ax4.set_ylabel("SKR (kbps)")
    ax4.set_xlabel("Elapsed Time (s)")
    ax4.set_ylim(bottom=-0.02)
    ax4.legend(loc="upper right", framealpha=0.9)

    save_figure(fig, OUTPUT_DIR / "dynamic_weather_timeline.png")

    # 2. Detailed SKR vs Channel Loss Trajectory
    fig2, ax = create_figure(
        title="SIMULATED ENVIRONMENT: SKR Degradation during Atmospheric Storm",
        xlabel="Total Channel Loss (dB)",
        ylabel="Secret Key Rate (kbps)"
    )
    scatter = ax.scatter(
        df["total_loss_db"],
        df["secret_key_rate_kbps"],
        c=df["cloud_coverage"],
        cmap="viridis",
        s=45,
        edgecolors="none",
        alpha=0.85
    )
    cbar = fig2.colorbar(scatter, ax=ax)
    cbar.set_label("Cloud Coverage Fraction", rotation=270, labelpad=15)
    ax.grid(True, alpha=0.3)
    save_figure(fig2, OUTPUT_DIR / "dynamic_weather_skr_loss.png")

    # 3. QBER Evolution with Loss Phase Diagram
    fig3, ax = create_figure(
        title="SIMULATED ENVIRONMENT: QBER Trajectory & Security Cutoff Boundary",
        xlabel="Total Channel Loss (dB)",
        ylabel="QBER (%)"
    )
    ax.scatter(df["total_loss_db"], df["qber_pct"], c=df["timestamp_s"], cmap="plasma", s=40, alpha=0.8)
    ax.axhline(11.0, color="red", linestyle="--", lw=2, label="Security Threshold (11.0%)")
    cbar = fig3.colorbar(plt.cm.ScalarMappable(cmap="plasma", norm=plt.Normalize(0, df["timestamp_s"].max())), ax=ax)
    cbar.set_label("Pass Time (s)", rotation=270, labelpad=15)
    ax.legend(loc="upper left")
    save_figure(fig3, OUTPUT_DIR / "dynamic_weather_qber_evolution.png")


if __name__ == "__main__":
    df = run_dynamic_weather_experiment(duration_sec=300, step_dt=1.0)
    plot_dynamic_weather_figures(df)
    print("  [SUCCESS] Experiment 8 execution completed.")
