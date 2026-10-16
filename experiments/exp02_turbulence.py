"""
exp02_turbulence.py — Experiment 2: Effect of Atmospheric Turbulence

Systematically sweeps atmospheric turbulence structure constant (Cn2) across
a wide range of turbulence regimes. Calculates channel loss, QBER, SKR, and
communication success rate. Generates CSV dataset and publication figures.
"""

from pathlib import Path
import sys
from typing import Optional, List

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

OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "turbulence"


def run_experiment_2(
    steps_per_level: int = 60,
    turbulence_levels: Optional = None,
    seed: int = 42
) -> pd.DataFrame:
    """Execute Experiment 2: Effect of Atmospheric Turbulence."""
    if turbulence_levels is None:
        # Sweep 10 turbulence structure parameter (Cn2) values from 1e-16 to 2e-13 m^(-2/3)
        turbulence_levels = [
            1.0e-16, 5.0e-16, 1.0e-15, 3.0e-15, 7.0e-15,
            1.5e-14, 3.0e-14, 7.0e-14, 1.2e-13, 2.0e-13
        ]

    print("=" * 70)
    print("  EXPERIMENT 2: EFFECT OF ATMOSPHERIC TURBULENCE")
    print(f"  Cn2 Levels ({len(turbulence_levels)}): {turbulence_levels[0]:.1e} to {turbulence_levels[-1]:.1e} m^(-2/3)")
    print(f"  Steps per level: {steps_per_level} | Seed: {seed}")
    print("=" * 70)

    np.random.seed(seed)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    station = GroundStationConfig()
    orbital = OrbitalModel(ground_station=station)
    optical = OpticalChannelModel()
    bb84 = BB84Model()

    # Fixed transmitter baseline settings
    power_pct = 70.0
    photon_rate_norm = 0.80
    divergence_norm = 0.25

    summary_records = []

    for idx, cn2 in enumerate(turbulence_levels):
        # Map Cn2 to normalized turbulence index [0, 1]
        log_cn2 = np.log10(cn2)
        turb_norm = float(np.clip((log_cn2 - (-16.0)) / ((-12.5) - (-16.0)), 0.0, 1.0))

        skr_list = []
        qber_list = []
        loss_list = []
        scint_list = []
        success_list = []

        for step in range(steps_per_level):
            # Satellite transit between 30 deg and 60 deg elevation
            current_time = 80.0 + step * 1.5
            sat_state = orbital.propagate(current_time)

            env_data = EnvironmentData(
                timestamp=sat_state.timestamp,
                temperature=25.0,
                humidity=50.0,
                ambient_light=300.0,
                vibration=0.008,
                cloud_factor=0.0,
                turbulence=turb_norm,
                data_source="SIMULATION",
                scenario_name="TURBULENCE_SWEEP"
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
                timestamp=sat_state.timestamp,
                anomaly_component=0.0
            )

            skr_bps = qkd_metrics.secret_key_rate
            qber = qkd_metrics.qber
            is_success = 1.0 if (skr_bps > 0.0 and qber < 0.11) else 0.0

            skr_list.append(skr_bps)
            qber_list.append(qber * 100.0)
            loss_list.append(channel_state.total_loss_db)
            scint_list.append(channel_state.scintillation_loss_db)
            success_list.append(is_success)

        mean_skr_kbps = float(np.mean(skr_list) / 1000.0)
        mean_qber = float(np.mean(qber_list))
        mean_loss = float(np.mean(loss_list))
        mean_scint = float(np.mean(scint_list))
        succ_rate = float(np.mean(success_list) * 100.0)

        record = {
            "level_index": idx + 1,
            "cn2_m_2_3": cn2,
            "log10_cn2": round(log_cn2, 2),
            "turbulence_index": round(turb_norm, 3),
            "mean_channel_loss_db": round(mean_loss, 2),
            "mean_scintillation_loss_db": round(mean_scint, 2),
            "mean_qber_pct": round(mean_qber, 2),
            "mean_skr_kbps": round(mean_skr_kbps, 3),
            "communication_success_rate_pct": round(succ_rate, 1)
        }
        summary_records.append(record)
        print(f"  [Cn2={cn2:.1e}] TurbIndex={turb_norm:.2f} | Loss={mean_loss:5.2f} dB | QBER={mean_qber:5.2f}% | SKR={mean_skr_kbps:5.3f} kbps | Success={succ_rate:5.1f}%")

    df = pd.DataFrame(summary_records)

    # 1. Save CSV
    csv_path = OUTPUT_DIR / "turbulence_sweep_metrics.csv"
    df.to_csv(csv_path, index=False)
    print(f"\n  [SAVED CSV] {csv_path}")

    # 2. Graph 1: Turbulence vs SKR
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.5))
    ax.plot(df["cn2_m_2_3"], df["mean_skr_kbps"], marker="o", color=PALETTE["secondary"], linewidth=2.2, markersize=6)
    ax.set_xscale("log")
    ax.set_title("Experiment 2: Atmospheric Turbulence vs Secret Key Rate (SKR)", fontweight="bold")
    ax.set_xlabel("Refractive Index Structure Constant $C_n^2$ ($m^{-2/3}$) [Log Scale]")
    ax.set_ylabel("Mean Secret Key Rate (kbps)")
    ax.grid(True, which="both", linestyle="--", alpha=0.6)
    save_figure(fig, OUTPUT_DIR, "turbulence_vs_skr.png")

    # 3. Graph 2: Turbulence vs QBER
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.5))
    ax.plot(df["cn2_m_2_3"], df["mean_qber_pct"], marker="s", color=PALETTE["accent"], linewidth=2.2, markersize=6, label="Mean QBER (%)")
    ax.axhline(y=11.0, color=PALETTE["danger"], linestyle="--", linewidth=1.8, label="BB84 Cutoff Threshold (11%)")
    ax.set_xscale("log")
    ax.set_title("Experiment 2: Atmospheric Turbulence vs Quantum Bit Error Rate", fontweight="bold")
    ax.set_xlabel("Refractive Index Structure Constant $C_n^2$ ($m^{-2/3}$) [Log Scale]")
    ax.set_ylabel("Mean QBER (%)")
    ax.grid(True, which="both", linestyle="--", alpha=0.6)
    ax.legend(loc="upper left")
    save_figure(fig, OUTPUT_DIR, "turbulence_vs_qber.png")

    # 4. Graph 3: Turbulence vs Channel Loss
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.5))
    ax.plot(df["cn2_m_2_3"], df["mean_channel_loss_db"], marker="^", color=PALETTE["primary"], linewidth=2.2, markersize=6, label="Total Channel Loss (dB)")
    ax.plot(df["cn2_m_2_3"], df["mean_scintillation_loss_db"], marker="v", color=PALETTE["purple"], linestyle=":", linewidth=1.8, markersize=5, label="Scintillation Loss (dB)")
    ax.set_xscale("log")
    ax.set_title("Experiment 2: Atmospheric Turbulence vs Optical Loss", fontweight="bold")
    ax.set_xlabel("Refractive Index Structure Constant $C_n^2$ ($m^{-2/3}$) [Log Scale]")
    ax.set_ylabel("Optical Loss (dB)")
    ax.grid(True, which="both", linestyle="--", alpha=0.6)
    ax.legend(loc="upper left")
    save_figure(fig, OUTPUT_DIR, "turbulence_vs_channel_loss.png")

    # 5. Graph 4: Turbulence vs Communication Success Rate
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.5))
    ax.plot(df["cn2_m_2_3"], df["communication_success_rate_pct"], marker="D", color=PALETTE["danger"], linewidth=2.2, markersize=6)
    ax.set_xscale("log")
    ax.set_ylim(-5, 105)
    ax.set_title("Experiment 2: Atmospheric Turbulence vs Communication Success Rate", fontweight="bold")
    ax.set_xlabel("Refractive Index Structure Constant $C_n^2$ ($m^{-2/3}$) [Log Scale]")
    ax.set_ylabel("Communication Success Rate (%)")
    ax.grid(True, which="both", linestyle="--", alpha=0.6)
    save_figure(fig, OUTPUT_DIR, "turbulence_vs_success_rate.png")

    return df


if __name__ == "__main__":
    run_experiment_2(steps_per_level=60, seed=42)
