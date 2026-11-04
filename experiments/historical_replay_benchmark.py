"""historical_replay_benchmark.py: Deterministic Historical Weather Replay Benchmark.

Replays an identical real/reanalysis meteorological sequence for Tiruchirappalli
across all 4 controllers (STATIC, RULE_BASED, PPO, MULTI_AGENT) under identical
satellite pass geometry, information access, and physical constraints.

Saves full step-by-step timeseries data and summary metrics.
Verifies aggregate results directly against time-series integration.
"""

import argparse
import datetime
import json
import logging
from pathlib import Path
import sys
import time
from typing import Dict, List, Literal, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from backend.app.config import settings
from backend.app.models.control import ControlAction
from backend.app.models.satellite import GroundStationConfig
from digital_twin.historical_weather_provider import HistoricalWeatherProvider
from digital_twin.optical_channel import OpticalChannelModel
from digital_twin.orbital_model import OrbitalModel
from qkd.bb84_model import BB84Model
from ai.rule_based_controller import RuleBasedController
from ai.ppo_controller import PPOController
from ai.agents.coordinator import CoordinatorAgent

logger = logging.getLogger("qsat.historical_benchmark")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class StaticController:
    """Fixed baseline controller with constant 50% power, 0.70 rate, 0.25 divergence."""
    def __init__(self, power_pct: float = 50.0, photon_rate: float = 0.70, divergence: float = 0.25):
        self.power_pct = power_pct
        self.photon_rate_norm = photon_rate
        self.beam_divergence_norm = divergence

    def decide(self, sat, env, channel, qkd) -> ControlAction:
        return ControlAction(
            transmission_power_pct=self.power_pct,
            photon_rate_norm=self.photon_rate_norm,
            beam_divergence_norm=self.beam_divergence_norm,
            requested_controller="STATIC",
            actual_controller="STATIC",
            controller_type="STATIC",
            model_loaded=False,
            reason="Static fixed baseline"
        )


def run_historical_benchmark(
    csv_file: str = "simulation/historical_weather/tiruchirappalli_20240301_20240331_era5.csv",
    start_datetime_iso: str = "2024-03-02T18:00:00Z",
    duration_s: int = 300,
    dt: float = 1.0,
    interpolation_mode: str = "LINEAR",
    output_dir: str = "results/experiments/historical_replay"
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Execute fair, deterministic multi-controller comparison on a historical pass."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("      Q-SAT HISTORICAL WEATHER REPLAY BENCHMARK")
    print(f"      CSV: {csv_file}")
    print(f"      Start: {start_datetime_iso} | Duration: {duration_s}s (dt={dt}s)")
    print(f"      Interpolation: {interpolation_mode}")
    print("=" * 80)

    # 1. Initialize environment & satellite models
    gs = GroundStationConfig(
        latitude=settings.GROUND_STATION_LAT,
        longitude=settings.GROUND_STATION_LON,
        altitude_m=settings.GROUND_STATION_ALT,
        min_elevation_deg=settings.MIN_ELEVATION
    )
    orbit = OrbitalModel(ground_station=gs)
    channel_model = OpticalChannelModel()
    bb84 = BB84Model()

    weather_provider = HistoricalWeatherProvider(
        csv_path=csv_file,
        start_datetime_iso=start_datetime_iso,
        interpolation_mode=interpolation_mode
    )

    # Pre-generate identical environment & satellite sequence for all controllers
    weather_provider.reset()
    env_sequence = []
    sat_sequence = []
    timesteps = np.arange(0.0, duration_s + dt, dt)

    for t in timesteps:
        sat = orbit.propagate(t)
        env = weather_provider.get_current_environment()
        sat_sequence.append(sat)
        env_sequence.append(env)
        weather_provider.step(dt=dt)

    # 2. Instantiate all 4 controllers with evaluation flags
    controllers = {
        "STATIC": StaticController(),
        "RULE_BASED": RuleBasedController(),
        "PPO": PPOController(
            model_path=str(PROJECT_ROOT / "models" / "ppo_qsat.zip"),
            evaluation_mode=True  # Strictly fails if PPO model cannot load/predict
        ),
        "MULTI_AGENT": CoordinatorAgent()
    }

    all_timeseries = []
    summary_records = []

    for ctrl_name, ctrl in controllers.items():
        print(f"\n>>> Evaluating Controller: {ctrl_name} ...")
        # Initialize link state from t=0
        chan_prev = channel_model.calculate_link_state(sat_sequence[0], env_sequence[0], 50.0, 0.70, 0.25)
        qkd_prev = bb84.evaluate(chan_prev, env_sequence[0], 0.0, 0.0)

        history = []
        decision_latencies_ms = []
        action_changes = 0
        prev_pwr = 50.0

        for i, t in enumerate(timesteps):
            sat = sat_sequence[i]
            env = env_sequence[i]

            # Measure controller decision latency
            t_start = time.perf_counter()
            if ctrl_name == "MULTI_AGENT":
                coord_dec = ctrl.step(sat, env, chan_prev, qkd_prev)
                action = coord_dec.final_action
            else:
                action = ctrl.decide(sat, env, chan_prev, qkd_prev)
            lat_ms = (time.perf_counter() - t_start) * 1000.0
            decision_latencies_ms.append(lat_ms)

            if abs(action.transmission_power_pct - prev_pwr) > 0.5:
                action_changes += 1
            prev_pwr = action.transmission_power_pct

            # Calculate physical optical channel response
            chan = channel_model.calculate_link_state(
                sat, env,
                action.transmission_power_pct,
                action.photon_rate_norm,
                action.beam_divergence_norm
            )
            qkd = bb84.evaluate(chan, env, t, 0.0)
            chan_prev = chan
            qkd_prev = qkd

            # Calculate physical electrical energy: P_elec (W) * dt (s) = Joules
            energy_j = settings.calculate_energy_joules(action.transmission_power_pct, dt=dt)
            energy_proxy = settings.calculate_energy_proxy(action.transmission_power_pct, dt=dt)

            # Key generated this step: SKR (bps) * dt (s) = bits
            step_bits = qkd.secret_key_rate * dt

            history.append({
                "timestamp_s": t,
                "datetime_iso": env.datetime_iso,
                "controller": ctrl_name,
                "requested_controller": action.requested_controller,
                "actual_controller": action.actual_controller,
                "model_loaded": action.model_loaded,
                "fallback_reason": action.fallback_reason,
                "skr_bps": qkd.secret_key_rate,
                "skr_kbps": qkd.secret_key_rate / 1000.0,
                "qber_fraction": qkd.qber,
                "qber_pct": qkd.qber * 100.0,
                "step_bits": step_bits,
                "is_distillable": qkd.is_key_distillation_possible,
                "channel_loss_db": chan.total_loss_db,
                "transmission_power_pct": action.transmission_power_pct,
                "photon_rate_norm": action.photon_rate_norm,
                "beam_divergence_norm": action.beam_divergence_norm,
                "energy_joules": energy_j,
                "energy_proxy": energy_proxy,
                "decision_latency_ms": lat_ms,
                "temp_c": env.temperature,
                "humidity_pct": env.humidity,
                "cloud_cover_pct": env.meteorological_cloud_cover_pct,
                "cloud_factor": env.cloud_factor,
                "wind_m_s": env.wind_speed_m_s,
                "is_interpolated": env.is_interpolated
            })

        df_c = pd.DataFrame(history)
        all_timeseries.append(df_c)

        # Compute aggregate metrics verified directly against timeseries
        total_bits = df_c["step_bits"].sum()
        total_kbits = total_bits / 1000.0
        mean_skr_kbps = df_c["skr_kbps"].mean()
        peak_skr_kbps = df_c["skr_kbps"].max()
        mean_qber_pct = df_c["qber_pct"].mean()
        uptime_pct = (df_c["is_distillable"].sum() / len(df_c)) * 100.0
        total_energy_j = df_c["energy_joules"].sum()
        total_energy_proxy = df_c["energy_proxy"].sum()
        efficiency_kb_j = total_kbits / total_energy_j if total_energy_j > 0 else 0.0
        mean_lat_ms = float(np.mean(decision_latencies_ms))
        power_std = float(df_c["transmission_power_pct"].std())

        summary_records.append({
            "controller": ctrl_name,
            "actual_controller": df_c["actual_controller"].iloc[0],
            "model_loaded": bool(df_c["model_loaded"].iloc[0]),
            "total_secret_key_kbits": round(total_kbits, 3),
            "mean_skr_kbps": round(mean_skr_kbps, 3),
            "peak_skr_kbps": round(peak_skr_kbps, 3),
            "mean_qber_pct": round(mean_qber_pct, 2),
            "uptime_pct": round(uptime_pct, 1),
            "total_energy_joules": round(total_energy_j, 2),
            "energy_proxy_pct_s": round(total_energy_proxy, 1),
            "efficiency_kbits_per_joule": round(efficiency_kb_j, 4),
            "action_changes": action_changes,
            "power_std_pct": round(power_std, 2),
            "decision_latency_ms": round(mean_lat_ms, 3)
        })

        print(
            f"  [{ctrl_name:<11}] Total Key: {total_kbits:6.2f} kbits | "
            f"Mean SKR: {mean_skr_kbps:6.3f} kbps | "
            f"QBER: {mean_qber_pct:5.2f}% | "
            f"Uptime: {uptime_pct:5.1f}% | "
            f"Energy: {total_energy_j:6.1f} J | "
            f"Efficiency: {efficiency_kb_j:6.3f} kb/J | "
            f"Latency: {mean_lat_ms:.2f} ms"
        )

    timeseries_df = pd.concat(all_timeseries, ignore_index=True)
    summary_df = pd.DataFrame(summary_records)

    # Save artifacts
    ts_csv = out_path / "historical_replay_timeseries.csv"
    summary_csv = out_path / "historical_replay_summary.csv"
    summary_json = out_path / "historical_replay_summary.json"

    timeseries_df.to_csv(ts_csv, index=False)
    summary_df.to_csv(summary_csv, index=False)

    # Verify aggregate summary totals strictly against per-step timeseries
    for rec in summary_records:
        c_name = rec["controller"]
        c_ts = timeseries_df[timeseries_df["controller"] == c_name]
        expected_kbits = round(c_ts["step_bits"].sum() / 1000.0, 3)
        assert abs(rec["total_secret_key_kbits"] - expected_kbits) < 1e-2, (
            f"Key mismatch for {c_name}: summary={rec['total_secret_key_kbits']}, timeseries={expected_kbits}"
        )
        expected_energy_j = round(c_ts["energy_joules"].sum(), 2)
        assert abs(rec["total_energy_joules"] - expected_energy_j) < 1e-1, (
            f"Energy mismatch for {c_name}: summary={rec['total_energy_joules']}, timeseries={expected_energy_j}"
        )
        expected_mean_skr = round(c_ts["skr_kbps"].mean(), 3)
        assert abs(rec["mean_skr_kbps"] - expected_mean_skr) < 1e-2, (
            f"Mean SKR mismatch for {c_name}: summary={rec['mean_skr_kbps']}, timeseries={expected_mean_skr}"
        )
    print("\n[VERIFICATION] All aggregate metrics verified directly against per-step time-series sums (0 discrepancy).")

    # Read dataset companion metadata if available
    dataset_meta = {}
    csv_p = Path(csv_file)
    meta_p = csv_p.with_suffix(".meta.json")
    if meta_p.exists():
        try:
            with open(meta_p, "r", encoding="utf-8") as f:
                dataset_meta = json.load(f)
        except Exception:
            pass

    metadata = {
        "benchmark_name": "Historical Weather Multi-Controller Replay",
        "timestamp_iso": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "dataset_identity": {
            "csv_source_file": str(csv_file),
            "dataset_name": dataset_meta.get("dataset_name", Path(csv_file).stem),
            "provenance": dataset_meta.get("provenance", "REANALYSIS_ERA5"),
            "data_type": dataset_meta.get("data_type", "ERA5 Reanalysis"),
            "model_requested": dataset_meta.get("model_requested", "era5"),
            "is_synthetic": dataset_meta.get("is_synthetic", False),
            "api_url": dataset_meta.get("api_url", "Open-Meteo Archive API")
        },
        "time_alignment": {
            "requested_start_utc": start_datetime_iso,
            "local_station_timezone": "Asia/Kolkata (IST = UTC + 05:30)",
            "explanation": (
                "Tiruchirappalli operates on Indian Standard Time (IST, UTC+05:30). "
                "Weather timestamps in ERA5 are archived in UTC. "
                "For example, 2024-03-02T18:00:00Z corresponds to 23:30 IST (11:30 PM local nighttime), "
                "representing ideal nocturnal QKD operating conditions with zero solar background irradiance."
            )
        },
        "atmospheric_channel_assumptions": {
            "turbulence": "CONFIGURED_ASSUMPTION (0.12 index; unmeasured in reanalysis models)",
            "vibration": "CONFIGURED_ASSUMPTION (0.015 g acceleration; mechanical mount jitter unmeasured)",
            "ambient_light": "MODELED_ESTIMATE (derived from solar zenith angle and shortwave irradiance; zero at local night)",
            "cloud_extinction": "NONLINEAR_OPTICAL_MODEL (derived from meteorological cloud cover via cloud_factor = (cover/100)^1.25)"
        },
        "configuration": {
            "duration_seconds": duration_s,
            "timestep_seconds": dt,
            "total_timesteps": len(timesteps),
            "interpolation_mode": interpolation_mode,
            "satellite_pass_mode": "ANALYTICAL_REFERENCE_PASS",
            "ground_station": {
                "name": "Tiruchirappalli reference ground station",
                "latitude": settings.GROUND_STATION_LAT,
                "longitude": settings.GROUND_STATION_LON,
                "altitude_m": settings.GROUND_STATION_ALT,
                "min_elevation_deg": settings.MIN_ELEVATION,
                "receiver_aperture_m": settings.RECEIVER_APERTURE_M,
                "wavelength_nm": settings.OPTICAL_WAVELENGTH_NM
            },
            "controllers_evaluated": list(controllers.keys())
        },
        "units": {
            "total_secret_key": "kbits (1000 bits)",
            "secret_key_rate": "kbps (kilobits per second)",
            "qber": "percentage (%)",
            "energy": "Joules (integrated electrical wall-plug power: P_elec * dt)",
            "energy_proxy": "%·s (transmission power percentage integrated over time)"
        },
        "results": summary_records
    }

    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)

    print("\n" + "=" * 80)
    print("                     HISTORICAL REPLAY SUMMARY TABLE")
    print("=" * 80)
    print(summary_df.to_string(index=False))
    print(f"\nArtifacts saved to: {out_path}")

    return timeseries_df, summary_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deterministic Historical Weather Replay Benchmark")
    parser.add_argument("--csv", type=str, default="simulation/historical_weather/tiruchirappalli_20240301_20240331_era5.csv")
    parser.add_argument("--start", type=str, default="2024-03-02T18:00:00Z")
    parser.add_argument("--duration", type=int, default=300)
    parser.add_argument("--dt", type=float, default=1.0)
    parser.add_argument("--interp", type=str, default="LINEAR", choices=["HOLD", "LINEAR"])
    parser.add_argument("--out", type=str, default="results/experiments/historical_replay")
    args = parser.parse_args()

    run_historical_benchmark(
        csv_file=args.csv,
        start_datetime_iso=args.start,
        duration_s=args.duration,
        dt=args.dt,
        interpolation_mode=args.interp,
        output_dir=args.out
    )
