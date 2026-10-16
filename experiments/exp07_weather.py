"""
exp07_weather.py — Experiment 7: Optical QKD Under Distinct Weather Scenarios

Evaluates complete QKD link performance under three standardized weather regimes:
1. CLEAR SKY (Calm, low extinction)
2. MODERATE (High humidity & haze)
3. SEVERE (Cloud cover & optical scattering)

Explicitly labeled: SIMULATED ENVIRONMENT.
Generates comparison table and publication plots.
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

OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "weather"

WEATHER_PROFILES = {
    "CLEAR": {
        "description": "Clear Sky (Calm Boundary Layer)",
        "temp_c": 25.0,
        "humidity_pct": 45.0,
        "ambient_lux": 300.0,
        "cloud_factor": 0.02,
        "turbulence": 0.05,
        "vibration": 0.008
    },
    "MODERATE": {
        "description": "Moderate Weather (High Humidity & Aerosol Haze)",
        "temp_c": 28.0,
        "humidity_pct": 85.0,
        "ambient_lux": 650.0,
        "cloud_factor": 0.35,
        "turbulence": 0.30,
        "vibration": 0.015
    },
    "SEVERE": {
        "description": "Severe Weather (Overcast Stratus Cloud & Rain Extinction)",
        "temp_c": 22.0,
        "humidity_pct": 95.0,
        "ambient_lux": 1500.0,
        "cloud_factor": 0.85,
        "turbulence": 0.65,
        "vibration": 0.040
    }
}


def run_experiment_7(steps_per_scenario: int = 120, seed: int = 42) -> pd.DataFrame:
    """Execute Experiment 7: Weather Scenarios Comparison."""
    print("=" * 70)
    print("  EXPERIMENT 7: OPTICAL QKD UNDER DISTINCT WEATHER SCENARIOS")
    print("  Data Provenance: SIMULATED ENVIRONMENT")
    print(f"  Scenarios: {list(WEATHER_PROFILES.keys())} | Steps each: {steps_per_scenario}")
    print("=" * 70)

    np.random.seed(seed)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    station = GroundStationConfig()
    orbital = OrbitalModel(ground_station=station)
    optical = OpticalChannelModel()
    bb84 = BB84Model()

    power_pct = 70.0
    photon_rate_norm = 0.80
    divergence_norm = 0.25

    summary_records = []
    raw_step_records = []

    for name, prof in WEATHER_PROFILES.items():
        skr_vals = []
        qber_vals = []
        loss_vals = []
        success_flags = []

        for step in range(steps_per_scenario):
            current_time = 60.0 + step * 1.5
            sat_state = orbital.propagate(current_time)

            env_data = EnvironmentData(
                timestamp=sat_state.timestamp,
                temperature=prof["temp_c"],
                humidity=prof["humidity_pct"],
                ambient_light=prof["ambient_lux"],
                vibration=prof["vibration"],
                cloud_factor=prof["cloud_factor"],
                turbulence=prof["turbulence"],
                data_source="SIMULATION",
                scenario_name=f"WEATHER_{name}"
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
            is_succ = 1.0 if (skr_bps > 0 and qber < 0.11) else 0.0

            skr_vals.append(skr_bps)
            qber_vals.append(qber * 100.0)
            loss_vals.append(channel_state.total_loss_db)
            success_flags.append(is_succ)

            raw_step_records.append({
                "scenario": name,
                "data_source": "SIMULATED ENVIRONMENT",
                "time_s": sat_state.timestamp,
                "elevation_deg": sat_state.elevation_deg,
                "skr_kbps": skr_bps / 1000.0,
                "qber_pct": qber * 100.0,
                "total_loss_db": channel_state.total_loss_db
            })

        rec = {
            "scenario": name,
            "data_source": "SIMULATED ENVIRONMENT",
            "description": prof["description"],
            "mean_skr_kbps": round(float(np.mean(skr_vals) / 1000.0), 3),
            "peak_skr_kbps": round(float(np.max(skr_vals) / 1000.0), 3),
            "mean_qber_pct": round(float(np.mean(qber_vals)), 2),
            "max_qber_pct": round(float(np.max(qber_vals)), 2),
            "mean_channel_loss_db": round(float(np.mean(loss_vals)), 2),
            "mean_power_pct": power_pct,
            "success_rate_pct": round(float(np.mean(success_flags) * 100.0), 1)
        }
        summary_records.append(rec)
        print(f"  [{name:8s}] SKR={rec['mean_skr_kbps']:5.3f} kbps | QBER={rec['mean_qber_pct']:5.2f}% | Loss={rec['mean_channel_loss_db']:5.2f} dB | Success={rec['success_rate_pct']:5.1f}%")

    df_summary = pd.DataFrame(summary_records)
    df_raw = pd.DataFrame(raw_step_records)

    # 1. Save CSVs
    summary_path = OUTPUT_DIR / "weather_comparison_summary.csv"
    raw_path = OUTPUT_DIR / "weather_raw_timesteps.csv"
    df_summary.to_csv(summary_path, index=False)
    df_raw.to_csv(raw_path, index=False)
    print(f"\n  [SAVED CSV] {summary_path}")

    # Colors for weather scenarios
    w_colors = [PALETTE["secondary"], PALETTE["accent"], PALETTE["danger"]]

    # 2. Graph 1: Weather vs SKR
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(6.5, 4.5))
    bars = ax.bar(df_summary["scenario"], df_summary["mean_skr_kbps"], color=w_colors, width=0.55, edgecolor="black", linewidth=0.8)
    ax.set_title("Experiment 7: Weather Regimes vs Secret Key Rate\n[SIMULATED ENVIRONMENT]", fontweight="bold")
    ax.set_ylabel("Mean Secret Key Rate (kbps)")
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.01, f"{yval:.3f}", ha="center", va="bottom", fontweight="bold")
    save_figure(fig, OUTPUT_DIR, "weather_vs_skr.png")

    # 3. Graph 2: Weather vs QBER
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(6.5, 4.5))
    bars = ax.bar(df_summary["scenario"], df_summary["mean_qber_pct"], color=w_colors, width=0.55, edgecolor="black", linewidth=0.8)
    ax.axhline(y=11.0, color=PALETTE["danger"], linestyle="--", linewidth=1.8, label="BB84 Cutoff (11%)")
    ax.set_title("Experiment 7: Weather Regimes vs Mean QBER\n[SIMULATED ENVIRONMENT]", fontweight="bold")
    ax.set_ylabel("Mean QBER (%)")
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    ax.legend(loc="upper left")
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.5, f"{yval:.1f}%", ha="center", va="bottom", fontweight="bold")
    save_figure(fig, OUTPUT_DIR, "weather_vs_qber.png")

    # 4. Graph 3: Weather vs Power (Preset Consumption)
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(6.5, 4.5))
    bars = ax.bar(df_summary["scenario"], df_summary["mean_power_pct"], color=PALETTE["primary"], width=0.55, edgecolor="black", linewidth=0.8)
    ax.set_title("Experiment 7: Weather Scenarios vs Transmitter Power\n[SIMULATED ENVIRONMENT]", fontweight="bold")
    ax.set_ylabel("Transmitter Power (%)")
    ax.set_ylim(0, 100)
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    save_figure(fig, OUTPUT_DIR, "weather_vs_power.png")

    # 5. Graph 4: Weather vs Success Rate
    fig, ax = create_figure(nrows=1, ncols=1, figsize=(6.5, 4.5))
    bars = ax.bar(df_summary["scenario"], df_summary["success_rate_pct"], color=w_colors, width=0.55, edgecolor="black", linewidth=0.8)
    ax.set_title("Experiment 7: Weather Regimes vs Communication Success Rate\n[SIMULATED ENVIRONMENT]", fontweight="bold")
    ax.set_ylabel("Communication Success Rate (%)")
    ax.set_ylim(0, 110)
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 1.5, f"{yval:.1f}%", ha="center", va="bottom", fontweight="bold")
    save_figure(fig, OUTPUT_DIR, "weather_vs_success_rate.png")

    return df_summary


if __name__ == "__main__":
    run_experiment_7()
