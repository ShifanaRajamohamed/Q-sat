"""Reward formulation for Q-SAT reinforcement learning environment.

Balances four critical trade-offs:
1. Performance: Maximizing asymptotic Secret Key Rate (SKR)
2. Security: Severe penalty as QBER approaches/exceeds 11% cutoff
3. Efficiency: Penalizing excessive laser transmission power consumption
4. Stability: Penalizing erratic actuator jitter across consecutive steps
"""

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class RewardBreakdown:
    total_reward: float
    skr_reward: float
    qber_penalty: float
    energy_penalty: float
    instability_penalty: float
    security_breach_penalty: float


def calculate_reward(
    secret_key_rate: float,
    qber: float,
    transmission_power_pct: float,
    delta_power: float,
    delta_photon_rate: float,
    delta_divergence: float,
    is_link_visible: bool,
    nominal_skr_bps: float = 20000.0
) -> RewardBreakdown:
    """Calculate multi-objective normalized scalar reward and component breakdown.
    
    Equations:
        R_skr = min(3.0, SKR / nominal_skr_bps)
        P_qber = (QBER / 0.11)^2.0 * 2.0
        P_energy = (Power% / 100.0) * 0.25
        P_instability = (|delta_P/100| + |delta_R| + |delta_D|) * 0.20
        P_breach = 5.0 if QBER >= 0.11 else 0.0
    """
    if not is_link_visible:
        # If link is unavailable, reward is based purely on conserving energy and remaining idle
        idle_power_penalty = (transmission_power_pct / 100.0) * 0.50
        return RewardBreakdown(
            total_reward=-idle_power_penalty,
            skr_reward=0.0,
            qber_penalty=0.0,
            energy_penalty=idle_power_penalty,
            instability_penalty=0.0,
            security_breach_penalty=0.0
        )

    # 1. Performance Reward (logarithmic / normalized linear)
    skr_norm = min(3.0, secret_key_rate / nominal_skr_bps)
    skr_reward = 2.0 * skr_norm

    # 2. QBER Penalty (super-linear growth as QBER approaches 11% BB84 cutoff)
    qber_ratio = qber / 0.110
    qber_penalty = float(np.clip((qber_ratio ** 2.0) * 2.5, 0.0, 10.0))

    # 3. Energy Consumption Penalty
    energy_penalty = (transmission_power_pct / 100.0) * 0.35

    # 4. Action Instability Penalty (smooth mechanical wear reduction)
    actuator_delta = abs(delta_power / 100.0) + abs(delta_photon_rate) + abs(delta_divergence)
    instability_penalty = float(actuator_delta * 0.20)

    # 5. Security Breach Disincentive
    security_breach_penalty = 3.0 if qber >= 0.110 or secret_key_rate <= 0.0 else 0.0

    total = skr_reward - qber_penalty - energy_penalty - instability_penalty - security_breach_penalty
    total_clamped = float(np.clip(total, -10.0, 10.0))

    return RewardBreakdown(
        total_reward=round(total_clamped, 4),
        skr_reward=round(skr_reward, 4),
        qber_penalty=round(qber_penalty, 4),
        energy_penalty=round(energy_penalty, 4),
        instability_penalty=round(instability_penalty, 4),
        security_breach_penalty=round(security_breach_penalty, 4)
    )
