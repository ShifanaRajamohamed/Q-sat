"""
exp17_statistics.py — Experiment 17: Statistical Validation Across Multiple Random Seeds

Executes rigorous Monte Carlo statistical evaluations (10 independent random seeds)
for each control paradigm to quantify variance, confidence intervals, and stability:
1. STATIC
2. RULE_BASED
3. PPO
4. MULTI_AGENT

Explicitly labeled: SIMULATED ENVIRONMENT.
Produces statistical distribution CSVs, boxplots, and confidence interval figures.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

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

OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "statistics"

SEEDS = [42, 101, 202, 303, 404, 505, 606, 707, 808, 909]


class StaticController:
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


def evaluate_single_run(controller_name: str, controller, seed: int, duration_s: int = 240) -> dict:
    np.random.seed(seed)
    gs = GroundStationConfig(latitude=10.7905, longitude=78.7047, altitude_m=80.0)
    orbit = OrbitalModel(ground_station=gs)
    channel_model = OpticalChannelModel()
    bb84 = BB84Model()

    dt = 1.0
    sat0 = orbit.propagate(0.0)
    env0 = EnvironmentData(
        timestamp=0.0, temperature=25.0, humidity=55.0, ambient_light=400.0,
        vibration=0.010, cloud_factor=0.08, turbulence=0.10, data_source="SIMULATION"
    )
    chan_prev = channel_model.calculate_link_state(sat0, env0, 50.0, 0.70, 0.25)
    qkd_prev = bb84.evaluate(chan_prev, env0, 0.0, 0.0)

    skr_history = []
    qber_history = []
    power_history = []
    distillable_history = []

    for t in np.arange(0.0, duration_s + dt, dt):
        sat = orbit.propagate(t)

        # Stochastic atmospheric dynamics unique to this seed
        cloud = float(np.clip(0.10 + 0.25 * np.sin(0.02 * t) ** 2 + 0.06 * np.random.randn(), 0.0, 0.95))
        turb = float(np.clip(0.12 + 0.20 * np.sin(0.015 * t) ** 2 + 0.04 * np.random.randn(), 0.0, 0.90))
        vib = float(np.clip(0.010 + 0.006 * np.random.rand(), 0.005, 0.050))
        lux = float(np.clip(400.0 + 100.0 * np.sin(0.025 * t), 100.0, 1500.0))

        env = EnvironmentData(
            timestamp=t, temperature=25.0, humidity=60.0, ambient_light=lux,
            vibration=vib, cloud_factor=cloud, turbulence=turb, data_source="SIMULATION"
        )

        if controller_name == "MULTI_AGENT":
            action = controller.step(sat, env, chan_prev, qkd_prev).final_action
        else:
            action = controller.decide(sat, env, chan_prev, qkd_prev)

        chan = channel_model.calculate_link_state(
            sat, env,
            action.transmission_power_pct,
            action.photon_rate_norm,
            action.beam_divergence_norm
        )
        qkd = bb84.evaluate(chan, env, t, anomaly_component=0.0)
        chan_prev = chan
        qkd_prev = qkd

        skr_history.append(qkd.secret_key_rate / 1e3)
        qber_history.append(qkd.qber * 100.0)
        power_history.append(action.transmission_power_pct)
        distillable_history.append(qkd.is_key_distillation_possible)

    total_kbits = sum(skr_history) * dt
    total_energy_j = sum((50.0 * (p / 100.0) / 0.15) * dt for p in power_history) / 1000.0
    uptime_pct = np.mean(distillable_history) * 100.0
    valid_qbers = [q for q, d in zip(qber_history, distillable_history) if d]
    mean_qber = np.mean(valid_qbers) if valid_qbers else np.mean(qber_history)

    return {
        "controller": controller_name,
        "seed": seed,
        "total_kbits": round(total_kbits, 3),
        "mean_skr_kbps": round(float(np.mean(skr_history)), 4),
        "mean_qber_pct": round(float(mean_qber), 2),
        "total_energy_j": round(total_energy_j, 2),
        "efficiency_kb_j": round(total_kbits / max(1e-6, total_energy_j), 3),
        "uptime_pct": round(float(uptime_pct), 1)
    }


def run_statistical_experiment() -> tuple[pd.DataFrame, pd.DataFrame]:
    print("=" * 70)
    print("  EXPERIMENT 17: STATISTICAL VALIDATION ACROSS MULTI-SEED RUNS")
    print("  Data Provenance: SIMULATED ENVIRONMENT")
    print(f"  Seeds: {SEEDS} (N={len(SEEDS)})")
    print("=" * 70)

    all_results = []
    controller_classes = {
        "STATIC": lambda: StaticController(),
        "RULE_BASED": lambda: RuleBasedController(),
        "PPO": lambda: PPOController(model_path=str(PROJECT_ROOT / "models" / "ppo_qsat.zip")),
        "MULTI_AGENT": lambda: CoordinatorAgent()
    }

    for c_name, c_factory in controller_classes.items():
        print(f"  Benchmarking {c_name:<12} across {len(SEEDS)} seeds...")
        for s in SEEDS:
            ctrl_inst = c_factory()
            res = evaluate_single_run(c_name, ctrl_inst, s, duration_s=240)
            all_results.append(res)

    df_runs = pd.DataFrame(all_results)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df_runs.to_csv(OUTPUT_DIR / "multi_seed_metrics.csv", index=False)
    print(f"  [SAVED CSV] {OUTPUT_DIR / 'multi_seed_metrics.csv'}")

    # Summary table with Mean, Std, and 95% Confidence Interval
    summary_list = []
    for c_name, grp in df_runs.groupby("controller"):
        n = len(grp)
        # Total key
        mean_k = grp["total_kbits"].mean()
        std_k = grp["total_kbits"].std()
        ci95_k = 1.96 * (std_k / np.sqrt(n))

        # Efficiency
        mean_eff = grp["efficiency_kb_j"].mean()
        std_eff = grp["efficiency_kb_j"].std()

        # Energy
        mean_e = grp["total_energy_j"].mean()
        std_e = grp["total_energy_j"].std()

        # QBER
        mean_q = grp["mean_qber_pct"].mean()
        std_q = grp["mean_qber_pct"].std()

        # Uptime
        mean_u = grp["uptime_pct"].mean()
        std_u = grp["uptime_pct"].std()

        summary_list.append({
            "Controller": c_name,
            "Total Key (kbits) Mean": round(mean_k, 2),
            "Total Key Std": round(std_k, 2),
            "Total Key 95% CI": round(ci95_k, 2),
            "Energy (J) Mean": round(mean_e, 2),
            "Energy Std": round(std_e, 2),
            "Efficiency (kb/J) Mean": round(mean_eff, 3),
            "Mean QBER (%)": round(mean_q, 2),
            "QBER Std": round(std_q, 2),
            "Uptime (%) Mean": round(mean_u, 1),
            "Uptime Std": round(std_u, 1)
        })

    summary_df = pd.DataFrame(summary_list)
    summary_df.to_csv(OUTPUT_DIR / "statistical_summary_table.csv", index=False)
    print(f"  [SAVED CSV] {OUTPUT_DIR / 'statistical_summary_table.csv'}")

    print("\n" + "=" * 90)
    print(f"{'Controller':<14} | {'Total Key (kbits)':<20} | {'Energy (J)':<16} | {'Efficiency':<12} | {'Uptime (%)':<14}")
    print("-" * 90)
    for _, r in summary_df.iterrows():
        key_str = f"{r['Total Key (kbits) Mean']:.1f} +/- {r['Total Key Std']:.1f}"
        eng_str = f"{r['Energy (J) Mean']:.1f} +/- {r['Energy Std']:.1f}"
        up_str = f"{r['Uptime (%) Mean']:.1f} +/- {r['Uptime Std']:.1f}%"
        print(f"{r['Controller']:<14} | {key_str:<20} | {eng_str:<16} | {r['Efficiency (kb/J) Mean']:>10.3f}   | {up_str:<14}")
    print("=" * 90 + "\n")

    return df_runs, summary_df


def plot_statistical_figures(df_runs: pd.DataFrame, summary_df: pd.DataFrame):
    colors = {
        "STATIC": "#64748b",
        "RULE_BASED": "#0284c7",
        "PPO": "#d97706",
        "MULTI_AGENT": "#059669"
    }

    # 1. Boxplots of Key Delivered and Energy Consumption across Seeds
    fig1, (ax1, ax2) = create_figure(nrows=1, ncols=2, figsize=(13, 5))
    controllers = ["STATIC", "RULE_BASED", "PPO", "MULTI_AGENT"]

    key_data = [df_runs[df_runs["controller"] == c]["total_kbits"] for c in controllers]
    bp1 = ax1.boxplot(key_data, tick_labels=controllers, patch_artist=True, medianprops=dict(color="black", lw=1.5))
    for patch, c in zip(bp1['boxes'], controllers):
        patch.set_facecolor(colors[c])
        patch.set_alpha(0.75)
    ax1.set_title("Distribution of Total Secret Key Delivered (kbits)", fontsize=11, weight="bold")
    ax1.set_ylabel("Secret Key (kbits)")
    ax1.grid(axis="y", alpha=0.3)

    energy_data = [df_runs[df_runs["controller"] == c]["total_energy_j"] for c in controllers]
    bp2 = ax2.boxplot(energy_data, tick_labels=controllers, patch_artist=True, medianprops=dict(color="black", lw=1.5))
    for patch, c in zip(bp2['boxes'], controllers):
        patch.set_facecolor(colors[c])
        patch.set_alpha(0.75)
    ax2.set_title("Distribution of Total Energy Consumed (Joules)", fontsize=11, weight="bold")
    ax2.set_ylabel("Energy (Joules)")
    ax2.grid(axis="y", alpha=0.3)

    fig1.suptitle("SIMULATED ENVIRONMENT: Monte Carlo Statistical Variance Across 10 Random Seeds", fontsize=13, weight="bold", y=1.02)
    save_figure(fig1, OUTPUT_DIR / "controller_boxplots.png")

    # 2. 95% Confidence Intervals for Secret Key Delivered
    fig2, ax = create_figure(
        title="SIMULATED ENVIRONMENT: Secret Key Yield with 95% Confidence Intervals",
        xlabel="Control Paradigm",
        ylabel="Mean Secret Key Delivered (kbits)"
    )
    means = summary_df["Total Key (kbits) Mean"]
    cis = summary_df["Total Key 95% CI"]
    c_names = summary_df["Controller"]
    c_colors = [colors[c] for c in c_names]

    ax.bar(c_names, means, yerr=cis, capsize=6, color=c_colors, edgecolor="black", lw=1.2, width=0.55, alpha=0.85)
    for i, (m, ci) in enumerate(zip(means, cis)):
        ax.text(i, m + ci + 1.5, f"{m:.1f} ± {ci:.1f}", ha="center", weight="bold", fontsize=10)
    ax.grid(axis="y", alpha=0.3)
    save_figure(fig2, OUTPUT_DIR / "confidence_intervals.png")


if __name__ == "__main__":
    df_runs, summary_df = run_statistical_experiment()
    plot_statistical_figures(df_runs, summary_df)
    print("  [SUCCESS] Experiment 17 execution completed.")
