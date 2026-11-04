"""exp16_ablation.py — Experiment 16: Hierarchical Multi-Agent Ablation Study.

Quantifies the isolated contribution of each agent within the hierarchical architecture
by evaluating four ablated variants against the complete multi-agent system:
1. Full Multi-Agent (Weather + Comm + Security + Coordinator)
2. w/o Weather Agent (blind to cloud/atmospheric extinction)
3. w/o Security Agent (blind to eavesdropping/channel anomalies)
4. w/o Communication Agent (static throughput targets)
5. Pure Static Baseline (no agents)

Explicitly labeled: SIMULATED ENVIRONMENT.
Produces standardized ablation tables and comparison outputs.
Architecture Note: This is a hierarchical heuristic rule-arbitration system, NOT Multi-Agent RL.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from ai.agents.coordinator import CoordinatorAgent
from backend.app.config import settings
from backend.app.models.control import ControlAction
from backend.app.models.environment import EnvironmentData
from backend.app.models.satellite import GroundStationConfig
from digital_twin.optical_channel import OpticalChannelModel
from digital_twin.orbital_model import OrbitalModel
from qkd.bb84_model import BB84Model

OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "ablation"


def run_ablation_study(duration_s: int = 300, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    print("=" * 75)
    print("  EXPERIMENT 16: HIERARCHICAL MULTI-AGENT ABLATION STUDY")
    print("  Data Provenance: SIMULATED ENVIRONMENT")
    print("  Architecture: Hierarchical rule-arbitrated multi-agent heuristic (NOT MARL)")
    print("  Variants: [Full_System, w/o Weather, w/o Security, w/o Comm, Static_Baseline]")
    print(f"  Duration: {duration_s}s | Seed: {seed}")
    print("=" * 75)

    np.random.seed(seed)
    gs = GroundStationConfig(
        name="Tiruchirappalli reference ground station",
        latitude=settings.GROUND_STATION_LAT,
        longitude=settings.GROUND_STATION_LON,
        altitude_m=settings.GROUND_STATION_ALT
    )
    orbit = OrbitalModel(ground_station=gs)
    channel_model = OpticalChannelModel()
    bb84 = BB84Model()

    # Instantiate ablated coordinator variants directly from CoordinatorAgent
    variants = {
        "Full Multi-Agent": CoordinatorAgent(enable_weather=True, enable_comm=True, enable_security=True),
        "w/o Weather Agent": CoordinatorAgent(enable_weather=False, enable_comm=True, enable_security=True),
        "w/o Security Agent": CoordinatorAgent(enable_weather=True, enable_comm=True, enable_security=False),
        "w/o Comm Agent": CoordinatorAgent(enable_weather=True, enable_comm=False, enable_security=True),
        "Static Baseline": CoordinatorAgent(enable_weather=False, enable_comm=False, enable_security=False)
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
            anomaly = 0.045  # 4.5% modeled anomaly component

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
        print(f"  Evaluating variant: {name:<22} ...")
        t0, sat0, env0, anom0 = pass_steps[0]
        chan_prev = channel_model.calculate_link_state(sat0, env0, 50.0, 0.70, 0.25)
        qkd_prev = bb84.evaluate(chan_prev, env0, 0.0, 0.0)

        variant_history = []
        for t, sat, env, anomaly in pass_steps:
            dec = coord.step(sat, env, chan_prev, qkd_prev)
            action = dec.final_action

            chan = channel_model.calculate_link_state(
                sat, env,
                action.transmission_power_pct,
                action.photon_rate_norm,
                action.beam_divergence_norm
            )
            qkd = bb84.evaluate(chan, env, t, anomaly_component=anomaly)
            chan_prev = chan
            qkd_prev = qkd

            # Physical electrical power in mW: (Optical_mW / wall_plug_efficiency)
            elec_mw = settings.power_pct_to_electrical_w(action.transmission_power_pct) * 1000.0

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

    print("\n" + "=" * 85)
    print(f"{'Variant':<24} | {'Total Key (kb)':<14} | {'Mean QBER':<10} | {'Energy (J)':<10} | {'Efficiency':<10} | {'Uptime':<8}")
    print("-" * 85)
    for _, r in summary_df.iterrows():
        print(f"{r['Variant']:<24} | {r['Total Secret Key (kbits)']:>14.2f} | {r['Mean QBER (%)']:>9.2f}% | {r['Total Energy (Joules)']:>10.2f} | {r['Energy Efficiency (kbits/J)']:>10.3f} | {r['Uptime (%)']:>7.1f}%")
    print("=" * 85 + "\n")

    return timeseries_df, summary_df


def try_plot_figures(timeseries_df: pd.DataFrame, summary_df: pd.DataFrame):
    """Attempt figure plotting if matplotlib is compatible with current numpy."""
    try:
        import matplotlib
        import matplotlib.pyplot as plt
        from experiments.plot_utils import create_figure, save_figure

        colors = {
            "Full Multi-Agent": "#059669",
            "w/o Weather Agent": "#f59e0b",
            "w/o Security Agent": "#ef4444",
            "w/o Comm Agent": "#8b5cf6",
            "Static Baseline": "#64748b"
        }

        fig1, (ax1, ax2) = create_figure(nrows=1, ncols=2, figsize=(13, 5))
        bar_cols = [colors.get(v, "#334155") for v in summary_df["Variant"]]

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
        print(f"  [SAVED FIGURE] {OUTPUT_DIR / 'ablation_metrics_bar.png'}")
    except Exception as e:
        print(f"  [NOTE] Plotting skipped due to environment library compatibility: {e}")
        print("  CSV and tabular metrics successfully generated and saved.")


if __name__ == "__main__":
    timeseries_df, summary_df = run_ablation_study(duration_s=300, seed=42)
    try_plot_figures(timeseries_df, summary_df)
    print("  [SUCCESS] Experiment 16 execution completed.")
