"""
exp04_distance.py — Experiment 4: Effect of Satellite-Ground Communication Distance

Systematically evaluates how Euclidean link range (500 km to 1800 km) alters
geometric diffraction path loss, QBER, Secret Key Rate, and key exchange availability.
Generates CSV dataset and publication plots.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from digital_twin.optical_channel import OpticalChannelModel
from qkd.bb84_model import BB84Model
from backend.app.models.satellite import SatelliteState
from backend.app.models.environment import EnvironmentData
from experiments.plot_utils import create_figure, save_figure, PALETTE

OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "distance"


def run_experiment_4(distances_km=None, seed: int = 42) -> pd.DataFrame:
    """Execute Experiment 4: Distance Sweep."""
    if distances_km is None:
        distances_km = np.linspace(500.0, 1800.0, 14)

    print("=" * 70)
    print("  EXPERIMENT 4: EFFECT OF SATELLITE-GROUND DISTANCE")
    print(f"  Range: {distances_km[0]:.0f} km to {distances_km[-1]:.0f} km ({len(distances_km)} points)")
    print("=" * 70)

    np.random.seed(seed)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    optical = OpticalChannelModel()
    bb84 = BB84Model()

    power_pct = 70.0
    photon_rate_norm = 0.80
    divergence_norm = 0.25

    records = []

    for d in distances_km:
        # Approximate elevation corresponding to distance from 500 km circular orbit
        # h = 500, R_E = 6371; d^2 = R_E^2 + (R_E+h)^2 - 2*R_E*(R_E+h)*cos(gamma)
        re = 6371.0
        h = 500.0
        # sin(elevation) approx:
        sin_elev = np.clip(((re + h)**2 - re**2 - d**2) / (2.0 * re * d), -1.0, 1.0)
        elev_deg = float(np.degrees(np.arcsin(sin_elev)))
        elev_deg = max(10.0, min(90.0, elev_deg))

        sat_state = SatelliteState(
            timestamp=0.0,
            satellite_name="Q-SAT-LEO-1",
            altitude_km=h,
            latitude=10.79,
            longitude=78.70,
            azimuth_deg=180.0,
            elevation_deg=elev_deg,
            slant_range_km=float(d),
            orbital_velocity_km_s=7.61,
            is_visible=True,
            pass_progress=0.5,
            link_status="TRACKING",
            pass_id=1,
            time_to_los_s=300.0
        )

        env_data = EnvironmentData(
            timestamp=0.0,
            temperature=25.0,
            humidity=50.0,
            ambient_light=300.0,
            vibration=0.008,
            cloud_factor=0.0,
            turbulence=0.05,
            data_source="SIMULATION",
            scenario_name="DISTANCE_SWEEP"
        )

        channel_state = optical.calculate_link_state(
            satellite=sat_state,
            environment=env_data,
            transmission_power_pct=power_pct,
            photon_rate_norm=photon_rate_norm,
            beam_divergence_norm=divergence_norm
        )

        qkd_metrics = bb84.evaluate(
            channel_state=channel_state,
            environment=env_data,
            timestamp=0.0,
            anomaly_component=0.0
        )

        skr_bps = qkd_metrics.secret_key_rate
        qber = qkd_metrics.qber
        success = 100.0 if (skr_bps > 0 and qber < 0.11) else 0.0

        record = {
            "slant_range_km": round(float(d), 1),
            "approx_elevation_deg": round(elev_deg, 1),
            "total_loss_db": round(channel_state.total_loss_db, 2),
            "fspl_loss_db": round(channel_state.fspl_loss_db, 2),
            "qber_pct": round(qber * 100.0, 2),
            "skr_bps": round(skr_bps, 2),
            "skr_kbps": round(skr_bps / 1000.0, 3),
            "success_rate_pct": success
        }
        records.append(record)
        print(f"  [Dist={d:6.1f} km] Loss={channel_state.total_loss_db:5.2f} dB | QBER={qber*100.0:5.2f}% | SKR={skr_bps/1000.0:5.3f} kbps | Success={success:5.1f}%")

    df = pd.DataFrame(records)

    # 1. Save CSV
    csv_path = OUTPUT_DIR / "distance_sweep_metrics.csv"
    df.to_csv(csv_path, index=False)
    print(f"\n  [SAVED CSV] {csv_path}")

    # 2. Graph 1: Distance vs SKR
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.5))
    ax.plot(df["slant_range_km"], df["skr_kbps"], marker="o", color=PALETTE["secondary"], linewidth=2.2, markersize=6)
    ax.set_title("Experiment 4: Communication Distance vs Secret Key Rate", fontweight="bold")
    ax.set_xlabel("Satellite-Ground Slant Range Distance (km)")
    ax.set_ylabel("Secret Key Rate (kbps)")
    ax.grid(True, linestyle="--", alpha=0.6)
    save_figure(fig, OUTPUT_DIR, "distance_vs_skr.png")

    # 3. Graph 2: Distance vs QBER
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.5))
    ax.plot(df["slant_range_km"], df["qber_pct"], marker="s", color=PALETTE["accent"], linewidth=2.2, markersize=6, label="Measured QBER (%)")
    ax.axhline(y=11.0, color=PALETTE["danger"], linestyle="--", linewidth=1.8, label="BB84 Cutoff (11%)")
    ax.set_title("Experiment 4: Communication Distance vs Quantum Bit Error Rate", fontweight="bold")
    ax.set_xlabel("Satellite-Ground Slant Range Distance (km)")
    ax.set_ylabel("QBER (%)")
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(loc="upper left")
    save_figure(fig, OUTPUT_DIR, "distance_vs_qber.png")

    # 4. Graph 3: Distance vs Channel Loss
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.5))
    ax.plot(df["slant_range_km"], df["total_loss_db"], marker="^", color=PALETTE["primary"], linewidth=2.2, markersize=6)
    ax.set_title("Experiment 4: Communication Distance vs Total Optical Loss", fontweight="bold")
    ax.set_xlabel("Satellite-Ground Slant Range Distance (km)")
    ax.set_ylabel("Total Optical Channel Loss (dB)")
    ax.grid(True, linestyle="--", alpha=0.6)
    save_figure(fig, OUTPUT_DIR, "distance_vs_channel_loss.png")

    # 5. Graph 4: Distance vs Success Rate
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.5))
    ax.plot(df["slant_range_km"], df["success_rate_pct"], marker="D", color=PALETTE["danger"], linewidth=2.2, markersize=6)
    ax.set_ylim(-5, 105)
    ax.set_title("Experiment 4: Communication Distance vs Link Availability", fontweight="bold")
    ax.set_xlabel("Satellite-Ground Slant Range Distance (km)")
    ax.set_ylabel("Communication Success Rate (%)")
    ax.grid(True, linestyle="--", alpha=0.6)
    save_figure(fig, OUTPUT_DIR, "distance_vs_success_rate.png")

    return df


if __name__ == "__main__":
    run_experiment_4()
