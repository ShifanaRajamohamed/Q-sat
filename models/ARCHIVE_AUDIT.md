# PPO Model Archive Audit & Integrity Documentation

## Overview
This document records the inspection, validation, and repair of `models/ppo_qsat.zip` in accordance with the Phase A requirements.

## 1. Original Archive State
- **Path**: `models/ppo_qsat_original_nested.zip` (Preserved intact)
- **Archive Contents**:
  ```
  ppo_qsat/
  ppo_qsat/data
  ppo_qsat/policy.optimizer.pth
  ppo_qsat/policy.pth
  ppo_qsat/pytorch_variables.pth
  ppo_qsat/system_info.txt
  ppo_qsat/_stable_baselines3_version
  ```
- **Root Cause of Load Failure**:
  The user manually extracted and re-zipped the model archive with an extra top-level folder `ppo_qsat/`.
  Stable-Baselines3's `PPO.load()` expects `data`, `policy.pth`, `pytorch_variables.pth`, and `_stable_baselines3_version` to reside directly at the archive root level.
  Because they were nested under `ppo_qsat/`, `PPO.load()` failed to find the files at root, causing previous versions of `PPOController` to silently fall back to `RuleBasedController`.

## 2. Repaired & Validated Archive
- **Path**: `models/ppo_qsat.zip`
- **Integrity Status**: Validated and Loadable (`is_loadable = True`)
- **Root Files**:
  - `data`: Model metadata and hyperparameters (JSON)
  - `policy.pth`: Actor-critic neural network weights (PyTorch)
  - `policy.optimizer.pth`: Adam optimizer states
  - `pytorch_variables.pth`: PyTorch device and learning rate schedule variables
  - `system_info.txt`: System training environment info
  - `_stable_baselines3_version`: `2.9.0`
- **Original Model Weights & Parameters**:
  **PRESERVED EXACTLY WITHOUT RETRAINING**. All byte-streams were transferred directly from the nested structure to the root level.

## 3. Observation & Action Space Verification
- **Observation Space**: `Box(low=0.0, high=1.0, shape=(15,), dtype=float32)`
  - Index 0: Satellite Elevation (normalized: $(elev + 10) / 100$)
  - Index 1: Slant Range (normalized: $range / 2000\text{ km}$)
  - Index 2: Temperature (normalized: $(temp + 20) / 70^\circ\text{C}$)
  - Index 3: Relative Humidity (normalized: $hum / 100$)
  - Index 4: Ambient Light (normalized: $lux / 100000$)
  - Index 5: Platform Vibration (normalized: $vib / 2.0\text{ g}$)
  - Index 6: Cloud Factor (normalized: $[0.0, 1.0]$)
  - Index 7: Turbulence Index (normalized: $[0.0, 1.0]$)
  - Index 8: Channel Loss (normalized: $loss / 60\text{ dB}$)
  - Index 9: QBER (normalized: $qber / 0.50$)
  - Index 10: Secret Key Rate (normalized: $SKR / 30000\text{ bps}$)
  - Index 11: Received Photon Rate (normalized: $rx\_rate / 500000\text{ photons/s}$)
  - Index 12: Current Transmission Power (normalized: $power\_pct / 100$)
  - Index 13: Current Photon Rate (normalized: $[0.0, 1.0]$)
  - Index 14: Current Beam Divergence (normalized: $[0.0, 1.0]$)
- **Action Space**: `Box(low=-1.0, high=1.0, shape=(3,), dtype=float32)`
  - Action 0: Normalized Transmission Power Delta ($[-20\%, +20\%]$)
  - Action 1: Normalized Photon Rate Delta ($[-0.20, +0.20]$)
  - Action 2: Normalized Beam Divergence Delta ($[-0.20, +0.20]$)

## 4. Package Compatibility Note
- Windows sandbox execution of `tensorboard` can trigger an unhandled lazy import of TensorFlow, causing `[Errno 13] Permission denied: 'C:\\Users\\HP\\.keras\\keras.json'`.
- `ai/model_validator.py` provides `sanitize_environment_for_sb3()` which neutralizes lazy TensorFlow imports before `stable_baselines3` loads PyTorch neural weights.

