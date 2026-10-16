"""
exp03_elevation.py — Experiment 3: Effect of Satellite Elevation Angle

Evaluates topocentric geometry and optical quantum channel performance across
elevation angles from 10° to 90° (zenith). Calculates slant distance, channel
attenuation, QBER, and Secret Key Rate. Generates CSV dataset and publication plots.
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
from backend.app.models.satellite import GroundStationConfig, SatelliteState
from backend.app.models.environment import EnvironmentData
from experiments.plot_utils import create_figure, save_figure, PALETTE

OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "elevation"


def run_experiment_3(elevation_angles=None, seed: int = 42) -> pd.DataFrame:
    """Execute Experiment 3: Elevation Angle Sweep."""
    if elevation_angles is None:
        elevation_angles = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0]

    print("=" * 70)
    print("  EXPERIMENT 3: EFFECT OF SATELLITE ELEVATION ANGLE")
    print(f"  Elevation Range: {elevation_angles[0]}° to {elevation_angles[-1]}° ({len(elevation_angles)} points)")
    print("=" * 70)

    np.random.seed(seed)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    station = GroundStationConfig()
    orbital = OrbitalModel(ground_station=station)
    optical = OpticalChannelModel()
    bb84 = BB84Model()

    # Fixed baseline setpoints
    power_pct = 70.0
    photon_rate_norm = 0.80
    divergence_norm = 0.25

    records = []

    for el in elevation_angles:
        slant_range_km = orbital.calculate_slant_range(el)
        airmass = optical.atmospheric_model.calculate_airmass(el)

        # Build synthetic satellite state at this elevation
        sat_state = SatelliteState(
            timestamp=0.0,
            satellite_name="Q-SAT-LEO-1",
            altitude_km=500.0,
            latitude=station.latitude,
            longitude=station.longitude,
            azimuth_deg=180.0,
            elevation_deg=el,
            slant_range_km=slant_range_km,
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
            scenario_name="ELEVATION_SWEEP"
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

        record = {
            "elevation_deg": el,
            "slant_range_km": round(slant_range_km, 2),
            "airmass": round(airmass, 2),
            "total_loss_db": round(channel_state.total_loss_db, 2),
            "fspl_loss_db": round(channel_state.fspl_loss_db, 2),
            "atmospheric_loss_db": round(channel_state.atmospheric_loss_db, 2),
            "qber_pct": round(qber * 100.0, 2),
            "skr_bps": round(skr_bps, 2),
            "skr_kbps": round(skr_bps / 1000.0, 3),
            "success_rate_pct": 100.0 if (skr_bps > 0 and qber < 0.11) else 0.0
        }
        records.append(record)
        print(f"  [El={el:4.1f}°] Range={slant_range_km:6.1f} km | Loss={channel_state.total_loss_db:5.2f} dB | QBER={qber*100.0:5.2f}% | SKR={skr_bps/1000.0:5.3f} kbps")

    df = pd.DataFrame(records)

    # 1. Save CSV
    csv_path = OUTPUT_DIR / "elevation_sweep_metrics.csv"
    df.to_csv(csv_path, index=False)
    print(f"\n  [SAVED CSV] {csv_path}")

    # 2. Graph 1: Elevation vs SKR
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.5))
    ax.plot(df["elevation_deg"], df["skr_kbps"], marker="o", color=PALETTE["secondary"], linewidth=2.2, markersize=6)
    ax.set_title("Experiment 3: Satellite Elevation vs Secret Key Rate", fontweight="bold")
    ax.set_xlabel("Satellite Elevation Angle (degrees)")
    ax.set_ylabel("Secret Key Rate (kbps)")
    ax.grid(True, linestyle="--", alpha=0.6)
    save_figure(fig, OUTPUT_DIR, "elevation_vs_skr.png")

    # 3. Graph 2: Elevation vs QBER
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.5))
    ax.plot(df["elevation_deg"], df["qber_pct"], marker="s", color=PALETTE["accent"], linewidth=2.2, markersize=6, label="Measured QBER (%)")
    ax.axhline(y=11.0, color=PALETTE["danger"], linestyle="--", linewidth=1.8, label="BB84 Cutoff (11%)")
    ax.set_title("Experiment 3: Satellite Elevation vs Quantum Bit Error Rate", fontweight="bold")
    ax.set_xlabel("Satellite Elevation Angle (degrees)")
    ax.set_ylabel("QBER (%)")
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(loc="upper right")
    save_figure(fig, OUTPUT_DIR, "elevation_vs_qber.png")

    # 4. Graph 3: Elevation vs Channel Loss
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.5))
    ax.plot(df["elevation_deg"], df["total_loss_db"], marker="^", color=PALETTE["primary"], linewidth=2.2, markersize=6, label="Total Channel Loss (dB)")
    ax.plot(df["elevation_deg"], df["fspl_loss_db"], marker="v", color=PALETTE["neutral"], linestyle=":", linewidth=1.8, markersize=5, label="Geometric Loss (dB)")
    ax.plot(df["elevation_deg"], df["atmospheric_loss_db"], marker="d", color=PALETTE["purple"], linestyle="--", linewidth=1.8, markersize=5, label="Atmospheric Extinction (dB)")
    ax.set_title("Experiment 3: Satellite Elevation vs Optical Channel Loss", fontweight="bold")
    ax.set_xlabel("Satellite Elevation Angle (degrees)")
    ax.set_ylabel("Optical Loss (dB)")
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(loc="upper right")
    save_figure(fig, OUTPUT_DIR, "elevation_vs_channel_loss.png")

    # 5. Graph 4: Elevation vs Slant Distance
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.5))
    ax.plot(df["elevation_deg"], df["slant_range_km"], marker="D", color=PALETTE["purple"], linewidth=2.2, markersize=6)
    ax.set_title("Experiment 3: Satellite Elevation vs Slant Range Distance", fontweight="bold")
    ax.set_xlabel("Satellite Elevation Angle (degrees)")
    ax.set_ylabel("Slant Range Distance (km)")
    ax.grid(True, linestyle="--", alpha=0.6)
    save_figure(fig, OUTPUT_DIR, "elevation_vs_distance.png")

    return df


if __name__ == "__main__":
    run_experiment_3()
