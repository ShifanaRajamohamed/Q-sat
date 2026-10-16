"""
exp10_final_comparison.py — Experiment 10: Comprehensive Multi-Controller Comparative Analysis

Benchmarks four distinct ground station control paradigms under identical orbital & atmospheric conditions:
1. STATIC: Non-adaptive baseline (fixed 50% power, 0.70 rate, 0.25 divergence)
2. RULE_BASED: Deterministic multi-threshold atmospheric adaptation heuristic
3. PPO: Deep Reinforcement Learning continuous policy (Stable-Baselines3)
4. MULTI_AGENT: Hierarchical multi-agent framework (Weather + Comm + Security + Coordinator)

Explicitly labeled: SIMULATED ENVIRONMENT.
Produces standardized comparative tables and 5 high-resolution publication figures.
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
from ai.rule_based_controller import RuleBasedController
from ai.ppo_controller import PPOController
from ai.agents.coordinator import CoordinatorAgent
from experiments.plot_utils import create_figure, save_figure, PALETTE

OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "final_comparison"


class StaticController:
    """Fixed baseline controller."""
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
            reason="Static fixed baseline"
        )


def run_comparative_study(duration_s: int = 300, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    print("=" * 70)
    print("  EXPERIMENT 10: COMPREHENSIVE MULTI-CONTROLLER BENCHMARK")
    print("  Data Provenance: SIMULATED ENVIRONMENT")
    print("  Paradigms: [STATIC, RULE_BASED, PPO, MULTI_AGENT]")
    print(f"  Duration: {duration_s}s | Seed: {seed}")
    print("=" * 70)

    np.random.seed(seed)
    gs = GroundStationConfig(station_id="GS-RESEARCH-01", latitude=10.7905, longitude=78.7047, altitude_m=80.0)
    orbit = OrbitalModel(ground_station=gs)
    channel_model = OpticalChannelModel()
    bb84 = BB84Model()

    controllers = {
        "STATIC": StaticController(),
        "RULE_BASED": RuleBasedController(),
        "PPO": PPOController(model_path=str(PROJECT_ROOT / "models" / "ppo_qsat.zip")),
        "MULTI_AGENT": CoordinatorAgent()
    }

    # Tracking records
    timeseries_records = []

    # Initialize environment sequence for pass
    env_sequence = []
    sat_sequence = []
    dt = 1.0
    for t in np.arange(0.0, duration_s + dt, dt):
        sat = orbit.propagate(t)
        # Realistic dynamic pass with mild-to-moderate atmospheric disturbance
        cloud = float(np.clip(0.08 + 0.25 * np.sin(0.02 * t) ** 2 + 0.04 * np.random.randn(), 0.0, 0.90))
        turb = float(np.clip(0.10 + 0.22 * np.sin(0.015 * t) ** 2 + 0.02 * np.random.randn(), 0.0, 0.85))
        hum = float(np.clip(55.0 + 15.0 * np.sin(0.01 * t), 30.0, 90.0))
        vib = float(np.clip(0.010 + 0.005 * np.random.rand(), 0.005, 0.040))
        lux = float(np.clip(400.0 + 80.0 * np.sin(0.03 * t), 100.0, 1200.0))

        env = EnvironmentData(
            timestamp=t,
            temperature=25.0,
            humidity=hum,
            ambient_light=lux,
            vibration=vib,
            cloud_factor=cloud,
            turbulence=turb,
            data_source="SIMULATION"
        )
        sat_sequence.append(sat)
        env_sequence.append(env)

    # Evaluate each controller across the identical sequence
    controller_results = {}
    for name, ctrl in controllers.items():
        print(f"  Evaluating {name:<12} ...")
        chan_prev = channel_model.calculate_link_state(sat_sequence[0], env_sequence[0], 50.0, 0.70, 0.25)
        qkd_prev = bb84.evaluate(chan_prev, env_sequence[0], 0.0, 0.0)

        history = []
        for i, t in enumerate(np.arange(0.0, duration_s + dt, dt)):
            sat = sat_sequence[i]
            env = env_sequence[i]

            # Decide action
            if name == "MULTI_AGENT":
                dec = ctrl.step(sat, env, chan_prev, qkd_prev)
                action = dec.final_action
            else:
                action = ctrl.decide(sat, env, chan_prev, qkd_prev)

            chan = channel_model.calculate_link_state(
                sat, env,
                action.transmission_power_pct,
                action.photon_rate_norm,
                action.beam_divergence_norm
            )
            qkd = bb84.evaluate(chan, env, t, 0.0)
            chan_prev = chan
            qkd_prev = qkd

            # Wall-plug power: (50mW * power_pct/100) / 0.15
            elec_mw = (50.0 * (action.transmission_power_pct / 100.0)) / 0.15

            history.append({
                "timestamp_s": t,
                "controller": name,
                "skr_kbps": qkd.secret_key_rate / 1e3,
                "qber_pct": qkd.qber * 100.0,
                "loss_db": chan.total_loss_db,
                "power_pct": action.transmission_power_pct,
                "elec_mw": elec_mw,
                "distillable": qkd.is_key_distillation_possible,
                "elevation_deg": sat.elevation_deg
            })

        controller_results[name] = pd.DataFrame(history)

    # Combine timeseries
    combined_df = pd.concat(controller_results.values(), ignore_index=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combined_df.to_csv(OUTPUT_DIR / "all_controllers_timeseries.csv", index=False)
    print(f"  [SAVED CSV] {OUTPUT_DIR / 'all_controllers_timeseries.csv'}")

    # Generate summary comparison table
    summary_rows = []
    for name, df_c in controller_results.items():
        total_kbits = df_c["skr_kbps"].sum() * dt
        total_energy_j = (df_c["elec_mw"].sum() * dt) / 1000.0
        distillable_pct = df_c["distillable"].mean() * 100.0
        valid_qber = df_c.loc[df_c["distillable"], "qber_pct"]
        mean_qber = valid_qber.mean() if len(valid_qber) > 0 else df_c["qber_pct"].mean()

        summary_rows.append({
            "Controller": name,
            "Total Secret Key (kbits)": round(total_kbits, 2),
            "Mean SKR (kbps)": round(df_c["skr_kbps"].mean(), 4),
            "Peak SKR (kbps)": round(df_c["skr_kbps"].max(), 4),
            "Mean Operational QBER (%)": round(mean_qber, 2),
            "Total Energy (Joules)": round(total_energy_j, 2),
            "Energy Efficiency (kbits/J)": round(total_kbits / max(1e-6, total_energy_j), 3),
            "Distillation Uptime (%)": round(distillable_pct, 1)
        })

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(OUTPUT_DIR / "all_controllers_summary.csv", index=False)
    print(f"  [SAVED CSV] {OUTPUT_DIR / 'all_controllers_summary.csv'}")

    print("\n" + "=" * 80)
    print(f"{'Controller':<14} | {'Total Key (kb)':<14} | {'Mean SKR':<10} | {'Peak SKR':<10} | {'Mean QBER':<10} | {'Energy (J)':<10} | {'Uptime':<8}")
    print("-" * 80)
    for _, r in summary_df.iterrows():
        print(f"{r['Controller']:<14} | {r['Total Secret Key (kbits)']:>14.2f} | {r['Mean SKR (kbps)']:>10.4f} | {r['Peak SKR (kbps)']:>10.4f} | {r['Mean Operational QBER (%)']:>9.2f}% | {r['Total Energy (Joules)']:>10.2f} | {r['Distillation Uptime (%)']:>7.1f}%")
    print("=" * 80 + "\n")

    return combined_df, summary_df


def plot_comparative_study_figures(combined_df: pd.DataFrame, summary_df: pd.DataFrame):
    colors = {
        "STATIC": "#64748b",       # Slate
        "RULE_BASED": "#0284c7",   # Blue
        "PPO": "#d97706",          # Amber
        "MULTI_AGENT": "#059669"   # Green
    }
    linestyles = {
        "STATIC": "--",
        "RULE_BASED": "-.",
        "PPO": ":",
        "MULTI_AGENT": "-"
    }

    # 1. Secret Key Rate Timeline
    fig1, ax1 = create_figure(
        title="SIMULATED ENVIRONMENT: Secret Key Rate Comparison Across Control Paradigms",
        xlabel="Elapsed Mission Time (seconds)",
        ylabel="Secret Key Rate (kbps)"
    )
    for name, group in combined_df.groupby("controller"):
        ax1.plot(group["timestamp_s"], group["skr_kbps"], label=name, color=colors[name], linestyle=linestyles[name], lw=2.2)
    ax1.legend(loc="upper right", framealpha=0.9)
    ax1.grid(True, alpha=0.3)
    save_figure(fig1, OUTPUT_DIR / "skr_comparison_timeline.png")

    # 2. QBER Timeline
    fig2, ax2 = create_figure(
        title="SIMULATED ENVIRONMENT: QBER Trajectory & Security Threshold Compliance",
        xlabel="Elapsed Mission Time (seconds)",
        ylabel="Quantum Bit Error Rate (%)"
    )
    for name, group in combined_df.groupby("controller"):
        ax2.plot(group["timestamp_s"], group["qber_pct"], label=name, color=colors[name], linestyle=linestyles[name], lw=2.0)
    ax2.axhline(11.0, color="#dc2626", lw=2.0, linestyle="--", label="Security Cutoff (11.0%)")
    ax2.set_ylim(-1, 55)
    ax2.legend(loc="upper right", framealpha=0.9)
    ax2.grid(True, alpha=0.3)
    save_figure(fig2, OUTPUT_DIR / "qber_comparison_timeline.png")

    # 3. Power Allocation Timeline
    fig3, ax3 = create_figure(
        title="SIMULATED ENVIRONMENT: Laser Transmission Power Dynamics Across Pass",
        xlabel="Elapsed Mission Time (seconds)",
        ylabel="Transmission Power (%)"
    )
    for name, group in combined_df.groupby("controller"):
        ax3.plot(group["timestamp_s"], group["power_pct"], label=name, color=colors[name], linestyle=linestyles[name], lw=2.0)
    ax3.legend(loc="upper right", framealpha=0.9)
    ax3.grid(True, alpha=0.3)
    save_figure(fig3, OUTPUT_DIR / "power_comparison_timeline.png")

    # 4. Multi-Metric Grouped Bar Comparison
    fig4, axes = create_figure(nrows=1, ncols=3, figsize=(15, 4.5))
    metrics = [
        ("Total Secret Key (kbits)", "kbits"),
        ("Total Energy (Joules)", "Joules"),
        ("Distillation Uptime (%)", "%")
    ]
    bar_cols = [colors[c] for c in summary_df["Controller"]]

    for ax, (metric_col, unit) in zip(axes, metrics):
        bars = ax.bar(summary_df["Controller"], summary_df[metric_col], color=bar_cols, edgecolor="black", lw=1.2, width=0.55)
        ax.set_title(metric_col, fontsize=11, weight="bold")
        ax.set_ylabel(unit)
        for b in bars:
            h = b.get_height()
            ax.annotate(f"{h:.1f}", xy=(b.get_x() + b.get_width() / 2, h), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", weight="bold")
        ax.grid(axis="y", alpha=0.3)

    fig4.suptitle("SIMULATED ENVIRONMENT: Benchmark Comparison Across 4 Control Paradigms", fontsize=13, weight="bold", y=1.03)
    save_figure(fig4, OUTPUT_DIR / "controller_radar_or_bar.png")

    # 5. Pareto Tradeoff: Secret Key Generated vs Energy Consumed
    fig5, ax5 = create_figure(
        title="SIMULATED ENVIRONMENT: Pareto Tradeoff — Key Production vs Energy Consumption",
        xlabel="Total Electrical Energy Consumed (Joules)",
        ylabel="Total Secret Key Delivered (kbits)"
    )
    for _, r in summary_df.iterrows():
        c_name = r["Controller"]
        ax5.scatter(r["Total Energy (Joules)"], r["Total Secret Key (kbits)"], color=colors[c_name], s=160, edgecolors="black", lw=1.5, zorder=5)
        ax5.annotate(
            f" {c_name}\n ({r['Energy Efficiency (kbits/J)']} kb/J)",
            xy=(r["Total Energy (Joules)"], r["Total Secret Key (kbits)"]),
            xytext=(10, -5),
            textcoords="offset points",
            fontweight="bold",
            fontsize=10
        )
    ax5.grid(True, alpha=0.3)
    save_figure(fig5, OUTPUT_DIR / "tradeoff_skr_vs_energy.png")


if __name__ == "__main__":
    combined_df, summary_df = run_comparative_study(duration_s=300, seed=42)
    plot_comparative_study_figures(combined_df, summary_df)
    print("  [SUCCESS] Experiment 10 execution completed.")
