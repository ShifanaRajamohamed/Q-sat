"""
exp16_ablation.py — Experiment 16: Hierarchical Multi-Agent Ablation Study

Quantifies the isolated contribution of each agent within the hierarchical architecture
by evaluating four ablated variants against the complete multi-agent system:
1. Full Multi-Agent (Weather + Comm + Security + Coordinator)
2. w/o Weather Agent (blind to cloud/atmospheric extinction)
3. w/o Security Agent (blind to eavesdropping/channel anomalies)
4. w/o Communication Agent (static throughput targets)
5. Pure Static Baseline (no agents)

Explicitly labeled: SIMULATED ENVIRONMENT.
Produces standardized ablation tables and publication comparison figures.
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
from backend.app.models.agents import WeatherAgentDecision, CommunicationAgentDecision, SecurityAgentDecision, CoordinatorDecision
from ai.agents.weather_agent import WeatherAgent
from ai.agents.communication_agent import CommunicationAgent
from ai.agents.security_agent import SecurityAgent
from experiments.plot_utils import create_figure, save_figure, PALETTE

OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "ablation"


class AblatableCoordinator:
    """Configurable Coordinator allowing selective ablation of domain agents."""

    def __init__(
        self,
        enable_weather: bool = True,
        enable_comm: bool = True,
        enable_security: bool = True,
        max_rate_of_change: float = 0.20
    ):
        self.enable_weather = enable_weather
        self.enable_comm = enable_comm
        self.enable_security = enable_security
        self.max_rate_of_change = max_rate_of_change

        self.weather_agent = WeatherAgent() if enable_weather else None
        self.comm_agent = CommunicationAgent() if enable_comm else None
        self.security_agent = SecurityAgent() if enable_security else None

        self.power_pct = 50.0
        self.photon_rate_norm = 0.70
        self.beam_divergence_norm = 0.25

    def step(self, sat, env, channel, qkd, anomaly_component: float = 0.0) -> ControlAction:
        if not sat.is_visible or sat.elevation_deg < 10.0:
            self.power_pct = 10.0
            self.photon_rate_norm = 0.10
            self.beam_divergence_norm = 0.30
            return ControlAction(
                transmission_power_pct=10.0,
                photon_rate_norm=0.10,
                beam_divergence_norm=0.30,
                controller_type="MULTI_AGENT",
                reason="Link standby"
            )

        # Baseline targets
        if self.enable_comm and self.comm_agent:
            comm_dec = self.comm_agent.analyze(sat, channel, qkd)
            target_power = comm_dec.target_power_pct
            target_rate = comm_dec.target_photon_rate_norm
        else:
            target_power = 50.0
            target_rate = 0.70

        target_div = 0.20

        # Weather arbitration
        if self.enable_weather and self.weather_agent:
            weather_dec = self.weather_agent.analyze(env)
            if weather_dec.severity in ["HIGH", "SEVERE"] and target_power > 80.0:
                target_power = min(85.0, target_power * 0.90)
                target_rate = min(0.75, target_rate * 0.85)

        # Security arbitration
        if self.enable_security and self.security_agent:
            sec_dec = self.security_agent.analyze(env, channel, qkd)
            if sec_dec.classification == "ANOMALY":
                target_rate = min(0.50, target_rate * 0.60)
                target_div = min(1.0, target_div * sec_dec.recommended_divergence_adj)

        # Vibration compensation
        if env.vibration > 0.40:
            target_div = min(1.0, max(target_div, 0.25 + 0.45 * env.vibration))

        # Rate clamping
        max_dp = self.max_rate_of_change * 100.0
        delta_p = float(np.clip(target_power - self.power_pct, -max_dp, max_dp))
        delta_r = float(np.clip(target_rate - self.photon_rate_norm, -self.max_rate_of_change, self.max_rate_of_change))
        delta_d = float(np.clip(target_div - self.beam_divergence_norm, -self.max_rate_of_change, self.max_rate_of_change))

        self.power_pct = float(np.clip(self.power_pct + delta_p, 10.0, 100.0))
        self.photon_rate_norm = float(np.clip(self.photon_rate_norm + delta_r, 0.05, 1.0))
        self.beam_divergence_norm = float(np.clip(self.beam_divergence_norm + delta_d, 0.10, 1.0))

        return ControlAction(
            transmission_power_pct=round(self.power_pct, 2),
            photon_rate_norm=round(self.photon_rate_norm, 4),
            beam_divergence_norm=round(self.beam_divergence_norm, 4),
            controller_type="MULTI_AGENT",
            reason="Ablated multi-agent execution"
        )


def run_ablation_study(duration_s: int = 300, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    print("=" * 70)
    print("  EXPERIMENT 16: HIERARCHICAL MULTI-AGENT ABLATION STUDY")
    print("  Data Provenance: SIMULATED ENVIRONMENT")
    print("  Variants: [Full_System, w/o Weather, w/o Security, w/o Comm, Static_Baseline]")
    print(f"  Duration: {duration_s}s | Seed: {seed}")
    print("=" * 70)

    np.random.seed(seed)
    gs = GroundStationConfig(latitude=10.7905, longitude=78.7047, altitude_m=80.0)
    orbit = OrbitalModel(ground_station=gs)
    channel_model = OpticalChannelModel()
    bb84 = BB84Model()

    variants = {
        "Full Multi-Agent": AblatableCoordinator(True, True, True),
        "w/o Weather Agent": AblatableCoordinator(False, True, True),
        "w/o Security Agent": AblatableCoordinator(True, True, False),
        "w/o Comm Agent": AblatableCoordinator(True, False, True),
        "Static Baseline": AblatableCoordinator(False, False, False)
    }

    # Pre-generate pass sequence with severe weather (t=80..130) and cyber attack (t=200..240)
    pass_steps = []
    dt = 1.0
    for t in np.arange(0.0, duration_s + dt, dt):
        sat = orbit.propagate(t)
        cloud = 0.08 + 0.08 * np.sin(0.02 * t) ** 2
        turb = 0.10 + 0.10 * np.sin(0.015 * t) ** 2
        vib = 0.010
        anomaly = 0.0

        if 80 <= t <= 130:
            cloud += 0.50 * np.sin(np.pi * (t - 80) / 50)
            turb += 0.35 * np.sin(np.pi * (t - 80) / 50)

        if 200 <= t <= 240:
            anomaly = 0.045  # 4.5% eavesdropping disturbance

        env = EnvironmentData(
            timestamp=t,
            temperature=25.0,
            humidity=60.0,
            ambient_light=450.0,
            vibration=vib,
            cloud_factor=float(np.clip(cloud, 0.0, 0.95)),
            turbulence=float(np.clip(turb, 0.0, 0.90)),
            data_source="SIMULATION"
        )
        pass_steps.append((t, sat, env, anomaly))

    timeseries_data = []
    summary_rows = []

    for name, coord in variants.items():
        print(f"  Running variant: {name:<22} ...")
        t0, sat0, env0, anom0 = pass_steps[0]
        chan_prev = channel_model.calculate_link_state(sat0, env0, 50.0, 0.70, 0.25)
        qkd_prev = bb84.evaluate(chan_prev, env0, 0.0, 0.0)

        variant_history = []
        for t, sat, env, anomaly in pass_steps:
            action = coord.step(sat, env, chan_prev, qkd_prev, anomaly_component=anomaly)
            chan = channel_model.calculate_link_state(
                sat, env,
                action.transmission_power_pct,
                action.photon_rate_norm,
                action.beam_divergence_norm
            )
            qkd = bb84.evaluate(chan, env, t, anomaly_component=anomaly)
            chan_prev = chan
            qkd_prev = qkd

            elec_mw = (50.0 * (action.transmission_power_pct / 100.0)) / 0.15

            variant_history.append({
                "timestamp_s": t,
                "variant": name,
                "skr_kbps": qkd.secret_key_rate / 1e3,
                "qber_pct": qkd.qber * 100.0,
                "power_pct": action.transmission_power_pct,
                "elec_mw": elec_mw,
                "distillable": qkd.is_key_distillation_possible
            })

        df_v = pd.DataFrame(variant_history)
        timeseries_data.append(df_v)

        # Compute summary metrics
        total_kbits = df_v["skr_kbps"].sum() * dt
        total_energy_j = (df_v["elec_mw"].sum() * dt) / 1000.0
        distillable_pct = df_v["distillable"].mean() * 100.0
        mean_qber = df_v.loc[df_v["distillable"], "qber_pct"].mean() if df_v["distillable"].any() else df_v["qber_pct"].mean()

        summary_rows.append({
            "Variant": name,
            "Total Secret Key (kbits)": round(total_kbits, 2),
            "Mean SKR (kbps)": round(df_v["skr_kbps"].mean(), 4),
            "Mean QBER (%)": round(mean_qber, 2),
            "Total Energy (Joules)": round(total_energy_j, 2),
            "Energy Efficiency (kbits/J)": round(total_kbits / max(1e-6, total_energy_j), 3),
            "Uptime (%)": round(distillable_pct, 1)
        })

    timeseries_df = pd.concat(timeseries_data, ignore_index=True)
    summary_df = pd.DataFrame(summary_rows)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timeseries_df.to_csv(OUTPUT_DIR / "ablation_timeseries.csv", index=False)
    summary_df.to_csv(OUTPUT_DIR / "ablation_study_summary.csv", index=False)
    print(f"  [SAVED CSV] {OUTPUT_DIR / 'ablation_study_summary.csv'}")

    print("\n" + "=" * 80)
    print(f"{'Variant':<24} | {'Total Key (kb)':<14} | {'Mean QBER':<10} | {'Energy (J)':<10} | {'Efficiency':<10} | {'Uptime':<8}")
    print("-" * 80)
    for _, r in summary_df.iterrows():
        print(f"{r['Variant']:<24} | {r['Total Secret Key (kbits)']:>14.2f} | {r['Mean QBER (%)']:>9.2f}% | {r['Total Energy (Joules)']:>10.2f} | {r['Energy Efficiency (kbits/J)']:>10.3f} | {r['Uptime (%)']:>7.1f}%")
    print("=" * 80 + "\n")

    return timeseries_df, summary_df


def plot_ablation_figures(timeseries_df: pd.DataFrame, summary_df: pd.DataFrame):
    colors = {
        "Full Multi-Agent": "#059669",      # Emerald
        "w/o Weather Agent": "#f59e0b",     # Amber
        "w/o Security Agent": "#ef4444",    # Red
        "w/o Comm Agent": "#8b5cf6",        # Purple
        "Static Baseline": "#64748b"        # Slate
    }

    # 1. Total Secret Key & Energy Efficiency Bar Chart
    fig1, (ax1, ax2) = create_figure(nrows=1, ncols=2, figsize=(13, 5))
    bar_cols = [colors[v] for v in summary_df["Variant"]]

    bars1 = ax1.bar(summary_df["Variant"], summary_df["Total Secret Key (kbits)"], color=bar_cols, edgecolor="black", lw=1.2, width=0.55)
    ax1.set_title("Total Secret Key Delivered (kbits)", fontsize=11, weight="bold")
    ax1.set_ylabel("Secret Key (kbits)")
    ax1.tick_params(axis="x", rotation=25)
    for b in bars1:
        h = b.get_height()
        ax1.annotate(f"{h:.1f}", xy=(b.get_x() + b.get_width() / 2, h), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", weight="bold")
    ax1.grid(axis="y", alpha=0.3)

    bars2 = ax2.bar(summary_df["Variant"], summary_df["Energy Efficiency (kbits/J)"], color=bar_cols, edgecolor="black", lw=1.2, width=0.55)
    ax2.set_title("Energy Efficiency (kbits per Joule)", fontsize=11, weight="bold")
    ax2.set_ylabel("Efficiency (kb/J)")
    ax2.tick_params(axis="x", rotation=25)
    for b in bars2:
        h = b.get_height()
        ax2.annotate(f"{h:.2f}", xy=(b.get_x() + b.get_width() / 2, h), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", weight="bold")
    ax2.grid(axis="y", alpha=0.3)

    fig1.suptitle("SIMULATED ENVIRONMENT: Multi-Agent Architecture Ablation Benchmark", fontsize=13, weight="bold", y=1.02)
    save_figure(fig1, OUTPUT_DIR / "ablation_metrics_bar.png")

    # 2. Secret Key Rate Timeline across Ablations
    fig2, ax = create_figure(
        title="SIMULATED ENVIRONMENT: SKR Trajectories Across Ablated Frameworks",
        xlabel="Elapsed Time (seconds)",
        ylabel="Secret Key Rate (kbps)"
    )
    for name, group in timeseries_df.groupby("variant"):
        lw = 2.4 if name == "Full Multi-Agent" else 1.8
        ls = "-" if name == "Full Multi-Agent" else ("--" if "Static" in name else "-.")
        ax.plot(group["timestamp_s"], group["skr_kbps"], label=name, color=colors[name], lw=lw, linestyle=ls)
    ax.legend(loc="upper right", framealpha=0.9)
    ax.grid(True, alpha=0.3)
    save_figure(fig2, OUTPUT_DIR / "ablation_skr_timeline.png")


if __name__ == "__main__":
    timeseries_df, summary_df = run_ablation_study(duration_s=300, seed=42)
    plot_ablation_figures(timeseries_df, summary_df)
    print("  [SUCCESS] Experiment 16 execution completed.")
