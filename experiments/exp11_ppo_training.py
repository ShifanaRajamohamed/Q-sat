"""
exp11_ppo_training.py — Experiment 11: PPO Reinforcement Learning Training Performance

Performs deterministic PPO policy training on QSATEnvironment while logging detailed
episodic rewards, loss metrics, and reward breakdown components.

Explicitly labeled: SIMULATED ENVIRONMENT.
Produces training log CSV, convergence metrics, and publication figures.
"""

from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback

from ai.environment import QSATEnvironment
from backend.app.models.environment import ScenarioType
from experiments.plot_utils import create_figure, save_figure, PALETTE

OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "ppo_training"


class TrainingMetricsCallback(BaseCallback):
    """Logs episode-level rewards, lengths, and reward breakdown statistics."""

    def __init__(self, verbose: int = 0):
        super().__init__(verbose)
        self.episode_rewards = []
        self.episode_lengths = []
        self.episode_skr_rewards = []
        self.episode_qber_penalties = []
        self.episode_energy_penalties = []
        
        self.curr_ep_reward = 0.0
        self.curr_ep_len = 0
        self.curr_skr_rew = 0.0
        self.curr_qber_pen = 0.0
        self.curr_energy_pen = 0.0

    def _on_step(self) -> bool:
        # Step reward
        reward = self.locals.get("rewards")[0]
        infos = self.locals.get("infos")[0]
        dones = self.locals.get("dones")[0]

        self.curr_ep_reward += reward
        self.curr_ep_len += 1

        breakdown = infos.get("reward_breakdown", {})
        self.curr_skr_rew += breakdown.get("skr_reward", 0.0)
        self.curr_qber_pen += breakdown.get("qber_penalty", 0.0)
        self.curr_energy_pen += breakdown.get("energy_penalty", 0.0)

        if dones:
            self.episode_rewards.append(self.curr_ep_reward)
            self.episode_lengths.append(self.curr_ep_len)
            self.episode_skr_rewards.append(self.curr_skr_rew)
            self.episode_qber_penalties.append(self.curr_qber_pen)
            self.episode_energy_penalties.append(self.curr_energy_pen)

            self.curr_ep_reward = 0.0
            self.curr_ep_len = 0
            self.curr_skr_rew = 0.0
            self.curr_qber_pen = 0.0
            self.curr_energy_pen = 0.0

        return True


def run_training_experiment(total_timesteps: int = 12000, seed: int = 42) -> pd.DataFrame:
    print("=" * 70)
    print("  EXPERIMENT 11: PPO REINFORCEMENT LEARNING CONVERGENCE")
    print("  Data Provenance: SIMULATED ENVIRONMENT")
    print(f"  Timesteps: {total_timesteps} | Seed: {seed} | Policy: MlpPolicy (64x64)")
    print("=" * 70)

    # Multi-scenario training environment
    train_env = QSATEnvironment(random_scenarios=True, seed=seed)

    policy_kwargs = dict(net_arch=dict(pi=[64, 64], vf=[64, 64]))
    model = PPO(
        "MlpPolicy",
        train_env,
        learning_rate=3e-4,
        n_steps=256,
        batch_size=64,
        n_epochs=4,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.005,
        policy_kwargs=policy_kwargs,
        verbose=0,
        seed=seed,
        device="cpu"
    )

    callback = TrainingMetricsCallback()
    start_time = time.time()
    model.learn(total_timesteps=total_timesteps, callback=callback)
    duration = time.time() - start_time
    print(f"  Training finished in {duration:.1f} seconds. Total Episodes: {len(callback.episode_rewards)}")

    # Construct DataFrame
    episodes = np.arange(1, len(callback.episode_rewards) + 1)
    df = pd.DataFrame({
        "episode": episodes,
        "episode_reward": callback.episode_rewards,
        "episode_length": callback.episode_lengths,
        "skr_reward": callback.episode_skr_rewards,
        "qber_penalty": callback.episode_qber_penalties,
        "energy_penalty": callback.episode_energy_penalties,
    })

    # Rolling averages
    window = min(10, len(df))
    df["reward_ma10"] = df["episode_reward"].rolling(window=window, min_periods=1).mean()
    df["reward_std10"] = df["episode_reward"].rolling(window=window, min_periods=1).std().fillna(0.0)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_DIR / "ppo_training_log.csv", index=False)
    print(f"  [SAVED CSV] {OUTPUT_DIR / 'ppo_training_log.csv'}")

    summary = pd.DataFrame([{
        "Total Timesteps": total_timesteps,
        "Total Episodes": len(df),
        "Initial Mean Reward (First 5)": round(df["episode_reward"].head(5).mean(), 2),
        "Final Mean Reward (Last 5)": round(df["episode_reward"].tail(5).mean(), 2),
        "Peak Episode Reward": round(df["episode_reward"].max(), 2),
        "Training Duration (s)": round(duration, 1)
    }])
    summary.to_csv(OUTPUT_DIR / "ppo_training_summary.csv", index=False)
    print(f"  [SAVED CSV] {OUTPUT_DIR / 'ppo_training_summary.csv'}")

    return df


def plot_training_figures(df: pd.DataFrame):
    # 1. Episode Reward Learning Curve with Rolling Mean & Confidence Band
    fig1, ax1 = create_figure(
        title="SIMULATED ENVIRONMENT: PPO Training Convergence Curve",
        xlabel="Training Episode",
        ylabel="Total Undiscounted Return"
    )
    ax1.plot(df["episode"], df["episode_reward"], color="#94a3b8", alpha=0.5, lw=1.2, label="Raw Episode Reward")
    ax1.plot(df["episode"], df["reward_ma10"], color=PALETTE["primary"], lw=2.4, label="Moving Average (10 eps)")
    ax1.fill_between(
        df["episode"],
        df["reward_ma10"] - df["reward_std10"],
        df["reward_ma10"] + df["reward_std10"],
        color=PALETTE["primary"],
        alpha=0.15,
        label="±1σ Reward Band"
    )
    ax1.legend(loc="lower right", framealpha=0.9)
    ax1.grid(True, alpha=0.3)
    save_figure(fig1, OUTPUT_DIR / "ppo_reward_curve.png")

    # 2. Multi-Objective Reward Decomposition during Training
    fig2, ax2 = create_figure(
        title="SIMULATED ENVIRONMENT: PPO Reward Components Decomposition",
        xlabel="Training Episode",
        ylabel="Cumulative Component Value"
    )
    ax2.plot(df["episode"], df["skr_reward"].rolling(5, min_periods=1).mean(), color=PALETTE["skr"], lw=2.0, label="SKR Reward (+)")
    ax2.plot(df["episode"], -df["qber_penalty"].rolling(5, min_periods=1).mean(), color=PALETTE["qber"], lw=2.0, label="QBER Penalty (-)")
    ax2.plot(df["episode"], -df["energy_penalty"].rolling(5, min_periods=1).mean(), color=PALETTE["accent"], lw=2.0, label="Energy Penalty (-)")
    ax2.axhline(0, color="black", lw=0.8, linestyle=":")
    ax2.legend(loc="center right", framealpha=0.9)
    ax2.grid(True, alpha=0.3)
    save_figure(fig2, OUTPUT_DIR / "ppo_reward_breakdown.png")


if __name__ == "__main__":
    df = run_training_experiment(total_timesteps=12000, seed=42)
    plot_training_figures(df)
    print("  [SUCCESS] Experiment 11 execution completed.")
