"""
exp01_baseline.py — Experiment 1: Baseline QKD Performance

Evaluates fixed-parameter baseline optical communication under a controlled
clear-sky scenario. Generates metrics table and high-resolution publication plots.
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

OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "baseline"


def run_experiment_1(steps: int = 150, seed: int = 42) -> pd.DataFrame:
    """Execute Experiment 1: Baseline QKD Performance."""
    print("=" * 70)
    print("  EXPERIMENT 1: BASELINE QKD PERFORMANCE")
    print("  Fixed Parameters: Power=70.0%, Rate=80.0 MHz, Divergence=25.0 µrad")
    print(f"  Duration: {steps} steps | Seed: {seed}")
    print("=" * 70)

    np.random.seed(seed)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize physical modules
    station = GroundStationConfig()
    orbital = OrbitalModel(ground_station=station)
    optical = OpticalChannelModel()
    bb84 = BB84Model()

    # Fixed transmitter baseline setpoints
    power_pct = 70.0
    photon_rate_norm = 0.80
    divergence_norm = 0.25

    records = []

    for step in range(steps):
        # Propagate orbit from t=60s (ascending pass)
        current_time = 60.0 + step * 1.0
        sat_state = orbital.propagate(current_time)

        # Fixed clear-sky microclimate
        env_data = EnvironmentData(
            timestamp=sat_state.timestamp,
            temperature=25.0,
            humidity=50.0,
            ambient_light=300.0,
            vibration=0.008,
            cloud_factor=0.0,
            turbulence=0.05,
            data_source="SIMULATION",
            scenario_name="CLEAR_SKY"
        )

        # Optical link budget
        channel_state = optical.calculate_link_state(
            satellite=sat_state,
            environment=env_data,
            transmission_power_pct=power_pct,
            photon_rate_norm=photon_rate_norm,
            beam_divergence_norm=divergence_norm
        )

        # BB84 Quantum Key Distribution
        qkd_metrics = bb84.evaluate(
            channel_state=channel_state,
            environment=env_data,
            timestamp=sat_state.timestamp,
            anomaly_component=0.0
        )

        skr_bps = qkd_metrics.secret_key_rate
        qber = qkd_metrics.qber
        success = 1.0 if (skr_bps > 0.0 and qber < 0.11) else 0.0

        records.append({
            "step": step,
            "time_s": sat_state.timestamp,
            "elevation_deg": round(sat_state.elevation_deg, 2),
            "slant_range_km": round(sat_state.slant_range_km, 1),
            "transmission_power_pct": power_pct,
            "total_loss_db": round(channel_state.total_loss_db, 2),
            "fspl_loss_db": round(channel_state.fspl_loss_db, 2),
            "atmospheric_loss_db": round(channel_state.atmospheric_loss_db, 2),
            "qber_pct": round(qber * 100.0, 2),
            "skr_bps": round(skr_bps, 2),
            "skr_kbps": round(skr_bps / 1000.0, 3),
            "success_flag": success
        })

    df = pd.DataFrame(records)

    # 1. Save CSV
    csv_path = OUTPUT_DIR / "baseline_metrics.csv"
    df.to_csv(csv_path, index=False)
    print(f"  [SAVED CSV] {csv_path}")

    # Summary Statistics
    summary = {
        "Metric": [
            "Mean Secret Key Rate (kbps)",
            "Peak Secret Key Rate (kbps)",
            "Mean QBER (%)",
            "Max QBER (%)",
            "Mean Channel Loss (dB)",
            "Min Channel Loss (dB)",
            "Communication Success Rate (%)",
            "Fixed Transmission Power (%)"
        ],
        "Value": [
            round(df["skr_kbps"].mean(), 3),
            round(df["skr_kbps"].max(), 3),
            round(df["qber_pct"].mean(), 2),
            round(df["qber_pct"].max(), 2),
            round(df["total_loss_db"].mean(), 2),
            round(df["total_loss_db"].min(), 2),
            round(df["success_flag"].mean() * 100.0, 1),
            power_pct
        ]
    }
    summary_df = pd.DataFrame(summary)
    summary_path = OUTPUT_DIR / "baseline_summary_table.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"  [SAVED SUMMARY TABLE] {summary_path}")

    # 2. Plot: Baseline SKR vs Time
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.5))
    ax.plot(df["time_s"], df["skr_kbps"], color=PALETTE["secondary"], linewidth=2.2, label="Secret Key Rate (SKR)")
    ax.set_title("Experiment 1: Baseline Secret Key Rate over Satellite Pass", fontweight="bold")
    ax.set_xlabel("Time Elapsed (seconds)")
    ax.set_ylabel("Secret Key Rate (kbps)")
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(loc="upper right")
    save_figure(fig, OUTPUT_DIR, "baseline_skr_vs_time.png")

    # 3. Plot: Baseline QBER vs Time
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.5))
    ax.plot(df["time_s"], df["qber_pct"], color=PALETTE["accent"], linewidth=2.2, label="Measured QBER (%)")
    ax.axhline(y=11.0, color=PALETTE["danger"], linestyle="--", linewidth=1.8, label="BB84 Cutoff Threshold (11%)")
    ax.set_title("Experiment 1: Baseline Quantum Bit Error Rate (QBER)", fontweight="bold")
    ax.set_xlabel("Time Elapsed (seconds)")
    ax.set_ylabel("QBER (%)")
    ax.set_ylim(0, 15)
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(loc="upper right")
    save_figure(fig, OUTPUT_DIR, "baseline_qber_vs_time.png")

    # 4. Plot: Baseline Channel Loss vs Time
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.5))
    ax.plot(df["time_s"], df["total_loss_db"], color=PALETTE["primary"], linewidth=2.2, label="Total Channel Loss (dB)")
    ax.plot(df["time_s"], df["fspl_loss_db"], color=PALETTE["neutral"], linestyle=":", linewidth=1.8, label="Free-Space Loss (dB)")
    ax.set_title("Experiment 1: Baseline Optical Channel Loss", fontweight="bold")
    ax.set_xlabel("Time Elapsed (seconds)")
    ax.set_ylabel("Optical Attenuation (dB)")
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(loc="upper right")
    save_figure(fig, OUTPUT_DIR, "baseline_channel_loss_vs_time.png")

    print("\n  Summary Table:")
    print(summary_df.to_string(index=False))
    return df


if __name__ == "__main__":
    run_experiment_1(steps=150, seed=42)
