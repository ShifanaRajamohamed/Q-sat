# Reinforcement Learning Controller (PPO)

This document describes the design, observation space, action mapping, reward function, and training methodology for the **Proximal Policy Optimization (PPO)** adaptive controller in Q-SAT.

---

## 1. Problem Formulation

In satellite-to-ground quantum communications, channel conditions fluctuate dynamically due to orbital geometry, atmospheric turbulence, cloud drift, and solar background flux. The control objective is to adaptively modulate transmitter parameters (optical power, pulse repetition frequency, and beam divergence half-angle) in real time to **maximize the Secret Key Rate (SKR)** while **strictly constraining the Quantum Bit Error Rate (QBER) below the $11.0\%$ BB84 cutoff threshold**.

We formulate this as a continuous-space Markov Decision Process (MDP) tuple $(\mathcal{S}, \mathcal{A}, \mathcal{P}, \mathcal{R}, \gamma)$:
- State space $\mathcal{S} \subset \mathbb{R}^{15}$
- Action space $\mathcal{A} \subset [-1, 1]^3$
- Reward function $\mathcal{R}: \mathcal{S} \times \mathcal{A} \to \mathbb{R}$
- Discount factor $\gamma = 0.99$

---

## 2. State & Observation Space ($\mathcal{S}$)

The observation vector $\mathbf{s}_t \in [0, 1]^{15}$ integrates orbital state, ground microclimate, optical link characteristics, QKD performance metrics, and current actuator states:

| Index | Feature | Dimension / Unit | Normalization Function |
|---|---|---|---|
| $0$ | Satellite Elevation $\theta$ | $\text{deg} \in [0, 90]$ | $s_0 = \theta / 90.0$ |
| $1$ | Satellite Azimuth $\phi$ | $\text{deg} \in [0, 360]$ | $s_1 = \phi / 360.0$ |
| $2$ | Slant Range $d$ | $\text{km} \in [500, 2000]$ | $s_2 = (d - 500) / 1500.0$ |
| $3$ | Ambient Temperature $T$ | $^\circ\text{C} \in [-10, 50]$ | $s_3 = (T + 10) / 60.0$ |
| $4$ | Relative Humidity $\text{RH}$ | $\% \in [0, 100]$ | $s_4 = \text{RH} / 100.0$ |
| $5$ | Ambient Illuminance $L$ | $\text{lux} \in [0, 10^5]$ | $s_5 = \log_{10}(1 + L) / 5.0$ |
| $6$ | Mount Vibration $\sigma_{\text{vibe}}$ | metric $\in [0, 1]$ | $s_6 = \min(1.0, \sigma_{\text{vibe}})$ |
| $7$ | Channel Total Loss $\mathcal{L}_{\text{tot}}$ | $\text{dB} \in [0, 80]$ | $s_7 = \mathcal{L}_{\text{tot}} / 80.0$ |
| $8$ | Quantum Bit Error Rate $e$ | fraction $\in [0, 0.5]$ | $s_8 = \min(1.0, e / 0.20)$ |
| $9$ | Raw Key Rate $R_{\text{raw}}$ | $\text{bps} \in [0, 10^6]$ | $s_9 = \log_{10}(1 + R_{\text{raw}}) / 6.0$ |
| $10$ | Sifted Key Rate $R_{\text{sift}}$ | $\text{bps} \in [0, 10^6]$ | $s_{10} = \log_{10}(1 + R_{\text{sift}}) / 6.0$ |
| $11$ | Secret Key Rate $R_{\text{SKR}}$ | $\text{bps} \in [0, 10^6]$ | $s_{11} = \log_{10}(1 + R_{\text{SKR}}) / 6.0$ |
| $12$ | Actuator: Laser Power $P_{\text{tx}}$ | $\text{mW} \in [5, 50]$ | $s_{12} = (P_{\text{tx}} - 5) / 45.0$ |
| $13$ | Actuator: Repetition Rate $R_{\text{rep}}$ | $\text{MHz} \in [10, 100]$ | $s_{13} = (R_{\text{rep}} - 10) / 90.0$ |
| $14$ | Actuator: Beam Divergence $\theta_{\text{div}}$ | $\mu\text{rad} \in [5, 50]$ | $s_{14} = (\theta_{\text{div}} - 5) / 45.0$ |

---

## 3. Continuous Action Space ($\mathcal{A}$)

The agent outputs a normalized 3-dimensional continuous action vector $\mathbf{a}_t \in [-1, 1]^3$, which is linearly mapped to physical actuator boundaries:

$$P_{\text{tx}} = 5.0 + 22.5 \cdot (a_0 + 1.0) \quad [\text{mW}] \in [5.0, 50.0]$$

$$R_{\text{rep}} = 10.0 + 45.0 \cdot (a_1 + 1.0) \quad [\text{MHz}] \in [10.0, 100.0]$$

$$\theta_{\text{div}} = 5.0 + 22.5 \cdot (a_2 + 1.0) \quad [\mu\text{rad}] \in [5.0, 50.0]$$

### 3.1 Rate-of-Change Limiting

To prevent actuator damage and high-frequency thermal cycling on satellite optical assemblies, inter-step changes are clamped to a maximum rate of $20\%$ per control step:

$$|\Delta a_i| \le 0.20 \quad \forall i \in \{0, 1, 2\}$$

---

## 4. Multi-Objective Reward Function ($\mathcal{R}$)

The reward function balances multiple competing operational objectives:

$$\mathcal{R}_t = w_{\text{skr}} \cdot \tilde{R}_{\text{skr}} - w_{\text{qber}} \cdot \Phi_{\text{qber}}(e) - w_{\text{power}} \cdot \tilde{P}_{\text{tx}} - w_{\text{jitter}} \cdot \|\mathbf{a}_t - \mathbf{a}_{t-1}\|_2^2 - w_{\text{abort}} \cdot \mathbf{1}_{\{e \ge 0.11\}}$$

### Reward Components & Hyperparameters:

1. **SKR Yield ($\tilde{R}_{\text{skr}}$)**: Normalized throughput benefit:
   $$\tilde{R}_{\text{skr}} = \frac{\log_{10}(1 + R_{\text{SKR}})}{\log_{10}(1 + R_{\text{max}})}, \quad w_{\text{skr}} = 2.0$$

2. **QBER Penalty Function ($\Phi_{\text{qber}}$)**: Progressive non-linear penalty:
   $$\Phi_{\text{qber}}(e) = \begin{cases} \left(\frac{e}{0.11}\right)^2, & e < 0.11 \\ 1.0 + 5.0 \cdot (e - 0.11), & e \ge 0.11 \end{cases}, \quad w_{\text{qber}} = 3.0$$

3. **Energy Efficiency ($\tilde{P}_{\text{tx}}$)**: Linear penalty for battery preservation:
   $$\tilde{P}_{\text{tx}} = \frac{P_{\text{tx}} - 5.0}{45.0}, \quad w_{\text{power}} = 0.20$$

4. **Actuator Stability ($\|\Delta \mathbf{a}\|^2$)**: Smoothness incentive:
   $$w_{\text{jitter}} = 0.50$$

5. **Security Cutoff Abort Penalty**:
   $$\mathbf{1}_{\{e \ge 0.11\}} = \begin{cases} 1, & \text{abort condition} \\ 0, & \text{secure session} \end{cases}, \quad w_{\text{abort}} = 5.0$$

---

## 5. PPO Architecture & Training Configuration

The PPO policy network is trained using **Stable-Baselines3** with the following hyperparameters:

- **Policy**: Actor-Critic Multi-Layer Perceptron (`MlpPolicy`)
- **Network Architecture**: Two hidden layers of 64 units each with $\tanh$ activations
- **Optimizer**: Adam ($\text{lr} = 3.0 \times 10^{-4}$)
- **Batch Size**: 64
- **Clip Range ($\epsilon$)**: 0.20
- **Entropy Coefficient**: 0.005 (encourages early exploratory variance)
- **Generalized Advantage Estimation (GAE)**: $\lambda = 0.95$, $\gamma = 0.99$
- **Training Epochs per Update**: 10
- **Model Checkpoint**: Saved to `models/ppo_qsat.zip`
