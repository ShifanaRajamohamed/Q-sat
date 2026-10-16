"""
exp09_static_vs_ppo.py — Experiment 9: Static Baseline vs PPO Controller

Performs head-to-head benchmarking between:
1. Static Baseline Controller (Fixed Actuators: 50% power, 0.70 rate, 0.25 div)
2. PPO Reinforcement Learning Controller (Dynamic policy optimizing SKR & power)

Under identical atmospheric disturbances across a full satellite pass.
Explicitly labeled: SIMULATED ENVIRONMENT.
Generates comprehensive comparative datasets and publication figures.
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
from backend.app.models.control import ControlAction
from ai.ppo_controller import PPOController
from experiments.plot_utils import create_figure, save_figure, PALETTE

OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "static_vs_ppo"


class StaticController:
    """Non-adaptive static baseline maintaining fixed default actuator settings."""
    def __init__(self, power_pct: float = 50.0, photon_rate: float = 0.70, divergence: float = 0.25):
        self.power_pct = power_pct
        self.photon_rate_norm = photon_rate
        self.beam_divergence_norm = divergence

    def decide(self, sat, env, channel, qkd) -> ControlAction:
        return ControlAction(
            transmission_power_pct=self.power_pct,
            photon_rate_norm=self.photon_rate_norm,
            beam_divergence_norm=self.beam_divergence_norm,
            controller_type="STATIC",
            reason="Static non-adaptive baseline"
        )


def run_comparison_experiment(duration_s: int = 300, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    print("=" * 70)
    print("  EXPERIMENT 9: STATIC BASELINE VS PPO CONTROLLER")
    print("  Data Provenance: SIMULATED ENVIRONMENT")
    print(f"  Duration: {duration_s}s | Seed: {seed} | Pass: LEO Polar (Trichy OGS)")
    print("=" * 70)

    np.random.seed(seed)
    gs = GroundStationConfig(station_id="GS-RESEARCH-01", latitude=10.7905, longitude=78.7047, altitude_m=80.0)
    orbit = OrbitalModel(ground_station=gs)
    channel_model = OpticalChannelModel()
    bb84 = BB84Model()

    static_ctrl = StaticController()
    ppo_ctrl = PPOController(model_path=str(PROJECT_ROOT / "models" / "ppo_qsat.zip"))

    records = []

    # State caches
    static_chan_prev = None
    static_qkd_prev = None
    ppo_chan_prev = None
    ppo_qkd_prev = None

    # Initial states at t=0
    sat_init = orbit.propagate(0.0)
    env_init = EnvironmentData(
        timestamp=0.0,
        temperature=25.0,
        humidity=65.0,
        ambient_light=450.0,
        vibration=0.012,
        cloud_factor=0.15,
        turbulence=0.20,
        data_source="SIMULATION"
    )

    static_chan_prev = channel_model.calculate_link_state(sat_init, env_init, 50.0, 0.70, 0.25)
    static_qkd_prev = bb84.evaluate(static_chan_prev, env_init, 0.0, 0.0)
    ppo_chan_prev = channel_model.calculate_link_state(sat_init, env_init, 50.0, 0.70, 0.25)
    ppo_qkd_prev = bb84.evaluate(ppo_chan_prev, env_init, 0.0, 0.0)

    dt = 1.0
    for t in np.arange(0.0, duration_s + dt, dt):
        sat = orbit.propagate(t)

        # Dynamic disturbance: varying cloud & atmospheric turbulence across pass
        cloud = float(np.clip(0.12 + 0.30 * np.sin(0.02 * t) ** 2 + 0.05 * np.random.randn(), 0.0, 0.95))
        turb = float(np.clip(0.15 + 0.25 * np.sin(0.015 * t) ** 2 + 0.03 * np.random.randn(), 0.0, 0.90))
        hum = float(np.clip(60.0 + 15.0 * np.sin(0.01 * t), 30.0, 95.0))
        vib = float(np.clip(0.012 + 0.008 * np.random.rand(), 0.005, 0.050))
        lux = float(np.clip(450.0 + 100.0 * np.sin(0.03 * t), 100.0, 1500.0))

        env = EnvironmentData(
            timestamp=t,
            temperature=26.0,
            humidity=hum,
            ambient_light=lux,
            vibration=vib,
            cloud_factor=cloud,
            turbulence=turb,
            data_source="SIMULATION"
        )

        # 1. Static Controller Step
        static_action = static_ctrl.decide(sat, env, static_chan_prev, static_qkd_prev)
        static_chan = channel_model.calculate_link_state(
            sat, env,
            static_action.transmission_power_pct,
            static_action.photon_rate_norm,
            static_action.beam_divergence_norm
        )
        static_qkd = bb84.evaluate(static_chan, env, t, 0.0)
        static_chan_prev = static_chan
        static_qkd_prev = static_qkd

        # 2. PPO Controller Step
        ppo_action = ppo_ctrl.decide(sat, env, ppo_chan_prev, ppo_qkd_prev)
        ppo_chan = channel_model.calculate_link_state(
            sat, env,
            ppo_action.transmission_power_pct,
            ppo_action.photon_rate_norm,
            ppo_action.beam_divergence_norm
        )
        ppo_qkd = bb84.evaluate(ppo_chan, env, t, 0.0)
        ppo_chan_prev = ppo_chan
        ppo_qkd_prev = ppo_qkd

        # Power calculation: Optical power [mW] = 50 mW * (power_pct / 100), Wall-plug electrical [mW] = P_opt / 0.15
        static_elec_mw = (50.0 * (static_action.transmission_power_pct / 100.0)) / 0.15
        ppo_elec_mw = (50.0 * (ppo_action.transmission_power_pct / 100.0)) / 0.15

        records.append({
            "timestamp_s": t,
            "elevation_deg": sat.elevation_deg,
            "cloud_factor": cloud,
            "turbulence": turb,
            # Static Metrics
            "static_skr_kbps": static_qkd.secret_key_rate / 1e3,
            "static_qber_pct": static_qkd.qber * 100.0,
            "static_loss_db": static_chan.total_loss_db,
            "static_power_pct": static_action.transmission_power_pct,
            "static_elec_mw": static_elec_mw,
            "static_distillable": static_qkd.is_key_distillation_possible,
            # PPO Metrics
            "ppo_skr_kbps": ppo_qkd.secret_key_rate / 1e3,
            "ppo_qber_pct": ppo_qkd.qber * 100.0,
            "ppo_loss_db": ppo_chan.total_loss_db,
            "ppo_power_pct": ppo_action.transmission_power_pct,
            "ppo_elec_mw": ppo_elec_mw,
            "ppo_distillable": ppo_qkd.is_key_distillation_possible,
        })

    df = pd.DataFrame(records)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_DIR / "static_vs_ppo_timeseries.csv", index=False)
    print(f"  [SAVED CSV] {OUTPUT_DIR / 'static_vs_ppo_timeseries.csv'}")

    # Aggregated Summary Table
    static_total_kbits = df["static_skr_kbps"].sum() * dt
    ppo_total_kbits = df["ppo_skr_kbps"].sum() * dt
    static_energy_j = (df["static_elec_mw"].sum() * dt) / 1000.0
    ppo_energy_j = (df["ppo_elec_mw"].sum() * dt) / 1000.0

    summary_data = [
        {
            "Metric": "Total Secret Bits Delivered (kbits)",
            "Static Baseline": round(static_total_kbits, 2),
            "PPO Controller": round(ppo_total_kbits, 2),
            "Relative Improvement (%)": round(((ppo_total_kbits - static_total_kbits) / max(1e-6, static_total_kbits)) * 100.0, 2),
        },
        {
            "Metric": "Mean Secret Key Rate (kbps)",
            "Static Baseline": round(df["static_skr_kbps"].mean(), 4),
            "PPO Controller": round(df["ppo_skr_kbps"].mean(), 4),
            "Relative Improvement (%)": round(((df["ppo_skr_kbps"].mean() - df["static_skr_kbps"].mean()) / max(1e-6, df["static_skr_kbps"].mean())) * 100.0, 2),
        },
        {
            "Metric": "Mean QBER (%)",
            "Static Baseline": round(df["static_qber_pct"].mean(), 2),
            "PPO Controller": round(df["ppo_qber_pct"].mean(), 2),
            "Relative Improvement (%)": round(((df["static_qber_pct"].mean() - df["ppo_qber_pct"].mean()) / max(1e-6, df["static_qber_pct"].mean())) * 100.0, 2),
        },
        {
            "Metric": "Total Energy Consumed (Joules)",
            "Static Baseline": round(static_energy_j, 2),
            "PPO Controller": round(ppo_energy_j, 2),
            "Relative Improvement (%)": round(((static_energy_j - ppo_energy_j) / static_energy_j) * 100.0, 2),
        },
        {
            "Metric": "Energy Efficiency (kbits / Joule)",
            "Static Baseline": round(static_total_kbits / max(1e-6, static_energy_j), 3),
            "PPO Controller": round(ppo_total_kbits / max(1e-6, ppo_energy_j), 3),
            "Relative Improvement (%)": round((((ppo_total_kbits / ppo_energy_j) - (static_total_kbits / static_energy_j)) / (static_total_kbits / static_energy_j)) * 100.0, 2),
        },
        {
            "Metric": "Link Availability / Distillable (%)",
            "Static Baseline": round(df["static_distillable"].mean() * 100.0, 1),
            "PPO Controller": round(df["ppo_distillable"].mean() * 100.0, 1),
            "Relative Improvement (%)": round((df["ppo_distillable"].mean() - df["static_distillable"].mean()) * 100.0, 2),
        }
    ]

    summary_df = pd.DataFrame(summary_data)
    summary_df.to_csv(OUTPUT_DIR / "comparison_metrics.csv", index=False)
    print(f"  [SAVED CSV] {OUTPUT_DIR / 'comparison_metrics.csv'}")

    for row in summary_data:
        print(f"  {row['Metric']:<40} | Static: {row['Static Baseline']:>8} | PPO: {row['PPO Controller']:>8} | Delta: {row['Relative Improvement (%)']:>+7.2f}%")

    return df, summary_df


def plot_comparison_figures(df: pd.DataFrame, summary_df: pd.DataFrame):
    t = df["timestamp_s"]

    # 1. Secret Key Rate Timeline Comparison
    fig1, ax1 = create_figure(
        title="SIMULATED ENVIRONMENT: Secret Key Rate — Static vs PPO Adaptive Control",
        xlabel="Time Elapsed (seconds)",
        ylabel="Secret Key Rate (kbps)"
    )
    ax1.plot(t, df["static_skr_kbps"], label="Static Baseline (50% Fixed Power)", color=PALETTE["neutral"], lw=2.0, linestyle="--")
    ax1.plot(t, df["ppo_skr_kbps"], label="PPO Adaptive Controller", color=PALETTE["skr"], lw=2.4)
    ax1.fill_between(t, df["static_skr_kbps"], df["ppo_skr_kbps"], where=(df["ppo_skr_kbps"] >= df["static_skr_kbps"]), color=PALETTE["skr"], alpha=0.15, label="PPO Advantage")
    ax1.legend(loc="upper right", framealpha=0.9)
    ax1.grid(True, alpha=0.3)
    save_figure(fig1, OUTPUT_DIR / "static_vs_ppo_skr_timeline.png")

    # 2. QBER Timeline Comparison
    fig2, ax2 = create_figure(
        title="SIMULATED ENVIRONMENT: QBER Trajectory — Static vs PPO Adaptive Control",
        xlabel="Time Elapsed (seconds)",
        ylabel="QBER (%)"
    )
    ax2.plot(t, df["static_qber_pct"], label="Static Baseline", color=PALETTE["neutral"], lw=2.0, linestyle="--")
    ax2.plot(t, df["ppo_qber_pct"], label="PPO Adaptive Controller", color=PALETTE["primary"], lw=2.2)
    ax2.axhline(11.0, color="red", lw=1.8, linestyle=":", label="Security Cutoff (11.0%)")
    ax2.legend(loc="upper right", framealpha=0.9)
    ax2.grid(True, alpha=0.3)
    save_figure(fig2, OUTPUT_DIR / "static_vs_ppo_qber_timeline.png")

    # 3. Transmission Power & Electrical Demand Timeline
    fig3, ax3 = create_figure(
        title="SIMULATED ENVIRONMENT: Transmission Power Allocation — Static vs PPO",
        xlabel="Time Elapsed (seconds)",
        ylabel="Laser Transmission Power (%)"
    )
    ax3.plot(t, df["static_power_pct"], label="Static Baseline (50% Fixed)", color=PALETTE["neutral"], lw=2.0, linestyle="--")
    ax3.plot(t, df["ppo_power_pct"], label="PPO Dynamic Allocation", color=PALETTE["accent"], lw=2.4)
    ax3.legend(loc="upper right", framealpha=0.9)
    ax3.grid(True, alpha=0.3)
    save_figure(fig3, OUTPUT_DIR / "static_vs_ppo_power_timeline.png")

    # 4. Summary Bar Comparison (Total Bits, Energy, Availability)
    fig4, axes = create_figure(nrows=1, ncols=3, figsize=(14, 4.5))
    metrics_to_plot = [
        ("Total Key (kbits)", df["static_skr_kbps"].sum(), df["ppo_skr_kbps"].sum(), "kbits", PALETTE["skr"]),
        ("Total Energy (J)", (df["static_elec_mw"].sum()) / 1000.0, (df["ppo_elec_mw"].sum()) / 1000.0, "Joules", PALETTE["accent"]),
        ("Link Availability (%)", df["static_distillable"].mean() * 100.0, df["ppo_distillable"].mean() * 100.0, "%", PALETTE["primary"])
    ]

    for ax, (name, static_val, ppo_val, unit, col) in zip(axes, metrics_to_plot):
        bars = ax.bar(["Static Baseline", "PPO Policy"], [static_val, ppo_val], color=[PALETTE["neutral"], col], width=0.55, edgecolor="black", linewidth=1.2)
        ax.set_title(name, fontsize=11, weight="bold")
        ax.set_ylabel(unit)
        for b in bars:
            h = b.get_height()
            ax.annotate(f"{h:.1f}", xy=(b.get_x() + b.get_width() / 2, h), xytext=(0, 4), textcoords="offset points", ha="center", va="bottom", weight="bold")
        ax.grid(axis="y", alpha=0.3)

    fig4.suptitle("SIMULATED ENVIRONMENT: Static vs PPO Performance Benchmark", fontsize=13, weight="bold", y=1.03)
    save_figure(fig4, OUTPUT_DIR / "static_vs_ppo_summary_bar.png")


if __name__ == "__main__":
    df, summary_df = run_comparison_experiment(duration_s=300, seed=42)
    plot_comparison_figures(df, summary_df)
    print("  [SUCCESS] Experiment 9 execution completed.")
