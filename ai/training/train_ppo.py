"""train_ppo.py: Training routine for Single-Agent PPO Controller on QSATEnvironment."""

import argparse
import json
from pathlib import Path
import sys
import time

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.evaluation import evaluate_policy

from ai.environment import QSATEnvironment
from backend.app.models.environment import ScenarioType


def train_ppo(
    total_timesteps: int = 15000,
    seed: int = 42,
    output_model_path: str = "models/ppo_qsat.zip",
    results_dir: str = "experiments/results"
) -> dict:
    """Train PPO on CPU using deterministic seeds, save weights, and evaluate metrics."""
    print("=" * 70)
    print("      Q-SAT PPO REINFORCEMENT LEARNING TRAINING (CPU)")
    print(f"      Timesteps: {total_timesteps} | Seed: {seed}")
    print("=" * 70)

    # 1. Instantiate Gymnasium environment with randomized scenario exposure
    train_env = QSATEnvironment(random_scenarios=True, seed=seed)
    eval_env = QSATEnvironment(scenario=ScenarioType.CLEAR_SKY, seed=seed + 100)

    # 2. Configure PPO Agent (Optimized for continuous action space on laptop CPU)
    policy_kwargs = dict(net_arch=dict(pi=[64, 64], vf=[64, 64]))
    model = PPO(
        "MlpPolicy",
        train_env,
        learning_rate=3e-4,
        n_steps=512,
        batch_size=64,
        n_epochs=5,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.005,
        policy_kwargs=policy_kwargs,
        verbose=1,
        seed=seed,
        device="cpu"
    )

    # 3. Train policy
    start_time = time.time()
    model.learn(total_timesteps=total_timesteps)
    training_duration = time.time() - start_time
    print(f"\nTraining completed in {training_duration:.2f} seconds.")

    # 4. Save model artifact
    save_path = Path(output_model_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(save_path))
    print(f"Model saved to: {save_path.resolve()}")

    # 5. Evaluate policy
    print("\nEvaluating trained PPO policy across 5 test episodes...")
    mean_reward, std_reward = evaluate_policy(model, eval_env, n_eval_episodes=5, deterministic=True)
    print(f"Mean Reward: {mean_reward:.2f} +/- {std_reward:.2f}")

    # 6. Save experiment metrics
    res_path = Path(results_dir)
    res_path.mkdir(parents=True, exist_ok=True)
    metrics = {
        "algorithm": "PPO",
        "total_timesteps": total_timesteps,
        "seed": seed,
        "training_duration_s": round(training_duration, 2),
        "mean_eval_reward": round(float(mean_reward), 4),
        "std_eval_reward": round(float(std_reward), 4),
        "model_file": str(save_path),
        "device": "cpu"
    }
    metrics_file = res_path / f"ppo_train_metrics_seed{seed}.json"
    with open(metrics_file, "w") as f:
        json.dump(metrics, f, indent=4)
    print(f"Results recorded in: {metrics_file}")

    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train PPO on QSATEnvironment")
    parser.add_argument("--timesteps", type=int, default=10000, help="Total training timesteps")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    parser.add_argument("--out", type=str, default="models/ppo_qsat.zip", help="Model output file")
    parser.add_argument("--results", type=str, default="experiments/results", help="Results directory")
    args = parser.parse_args()

    train_ppo(total_timesteps=args.timesteps, seed=args.seed, output_model_path=args.out, results_dir=args.results)
