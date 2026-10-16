"""
exp06_power.py — Experiment 6: Effect of Optical Transmission Power

Evaluates the trade-off between transmitter laser optical power (10% to 100%),
secret key rate, QBER suppression, and electrical energy cost on satellite.
Generates CSV dataset and 4 publication plots.
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

OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "power"


def run_experiment_6(power_levels=None, seed: int = 42) -> pd.DataFrame:
    """Execute Experiment 6: Transmission Power Sweep."""
    if power_levels is None:
        power_levels = np.linspace(10.0, 100.0, 10)  # 10% to 100% (5 mW to 50 mW equivalent)

    print("=" * 70)
    print("  EXPERIMENT 6: TRANSMISSION POWER VS PERFORMANCE & ENERGY")
    print(f"  Power Range: {power_levels[0]:.0f}% to {power_levels[-1]:.0f}% ({len(power_levels)} levels)")
    print("=" * 70)

    np.random.seed(seed)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    station = GroundStationConfig()
    orbital = OrbitalModel(ground_station=station)
    optical = OpticalChannelModel()
    bb84 = BB84Model()

    # Propagate to a representative mid-pass elevation (~45 deg)
    sat_state = orbital.propagate(120.0)

    photon_rate_norm = 0.80
    divergence_norm = 0.25

    records = []

    for p in power_levels:
        # Energy cost index: electrical consumption scales with transmission power
        # Nominal satellite laser diode wall-plug efficiency ~15%
        power_mw = float(p) * 0.50  # 100% -> 50 mW optical
        electrical_power_mw = power_mw / 0.15

        env_data = EnvironmentData(
            timestamp=sat_state.timestamp,
            temperature=25.0,
            humidity=50.0,
            ambient_light=300.0,
            vibration=0.008,
            cloud_factor=0.0,
            turbulence=0.05,
            data_source="SIMULATION",
            scenario_name="POWER_SWEEP"
        )

        channel_state = optical.calculate_link_state(
            satellite=sat_state,
            environment=env_data,
            transmission_power_pct=float(p),
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
        success = 100.0 if (skr_bps > 0 and qber < 0.11) else 0.0

        records.append({
            "transmission_power_pct": float(p),
            "optical_power_mw": round(power_mw, 1),
            "electrical_power_mw": round(electrical_power_mw, 1),
            "received_photon_rate_hz": round(channel_state.received_photon_rate, 1),
            "total_loss_db": round(channel_state.total_loss_db, 2),
            "snr_db": round(channel_state.snr_db, 2),
            "qber_pct": round(qber * 100.0, 2),
            "skr_bps": round(skr_bps, 2),
            "skr_kbps": round(skr_bps / 1000.0, 3),
            "success_rate_pct": success
        })
        print(f"  [Power={p:5.1f}% ({power_mw:4.1f} mW)] SNR={channel_state.snr_db:5.1f} dB | QBER={qber*100.0:5.2f}% | SKR={skr_bps/1000.0:5.3f} kbps | ElecPower={electrical_power_mw:5.1f} mW")

    df = pd.DataFrame(records)

    # 1. Save CSV
    csv_path = OUTPUT_DIR / "power_sweep_metrics.csv"
    df.to_csv(csv_path, index=False)
    print(f"\n  [SAVED CSV] {csv_path}")

    # 2. Graph 1: Power vs SKR
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.5))
    ax.plot(df["transmission_power_pct"], df["skr_kbps"], marker="o", color=PALETTE["secondary"], linewidth=2.2, markersize=6)
    ax.set_title("Experiment 6: Transmission Power vs Secret Key Rate", fontweight="bold")
    ax.set_xlabel("Transmitter Laser Power (% of Maximum 50 mW)")
    ax.set_ylabel("Secret Key Rate (kbps)")
    ax.grid(True, linestyle="--", alpha=0.6)
    save_figure(fig, OUTPUT_DIR, "power_vs_skr.png")

    # 3. Graph 2: Power vs QBER
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.5))
    ax.plot(df["transmission_power_pct"], df["qber_pct"], marker="s", color=PALETTE["accent"], linewidth=2.2, markersize=6)
    ax.axhline(y=11.0, color=PALETTE["danger"], linestyle="--", linewidth=1.8, label="BB84 Cutoff (11%)")
    ax.set_title("Experiment 6: Transmission Power vs Quantum Bit Error Rate", fontweight="bold")
    ax.set_xlabel("Transmitter Laser Power (%)")
    ax.set_ylabel("QBER (%)")
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(loc="upper right")
    save_figure(fig, OUTPUT_DIR, "power_vs_qber.png")

    # 4. Graph 3: Power vs Success Rate
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.5))
    ax.plot(df["transmission_power_pct"], df["success_rate_pct"], marker="D", color=PALETTE["primary"], linewidth=2.2, markersize=6)
    ax.set_ylim(-5, 105)
    ax.set_title("Experiment 6: Transmission Power vs Link Availability", fontweight="bold")
    ax.set_xlabel("Transmitter Laser Power (%)")
    ax.set_ylabel("Success Rate (%)")
    ax.grid(True, linestyle="--", alpha=0.6)
    save_figure(fig, OUTPUT_DIR, "power_vs_success_rate.png")

    # 5. Graph 4: Power vs Energy Cost
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(7.5, 4.5))
    ax.plot(df["transmission_power_pct"], df["electrical_power_mw"], marker="^", color=PALETTE["danger"], linewidth=2.2, markersize=6)
    ax.set_title("Experiment 6: Transmission Power vs Satellite Electrical Energy Cost", fontweight="bold")
    ax.set_xlabel("Transmitter Laser Power (%)")
    ax.set_ylabel("Electrical Consumption (mW)")
    ax.grid(True, linestyle="--", alpha=0.6)
    save_figure(fig, OUTPUT_DIR, "power_vs_energy_cost.png")

    return df


if __name__ == "__main__":
    run_experiment_6()
