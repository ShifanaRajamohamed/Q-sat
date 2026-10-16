"""Control Service: Singleton controller manager supporting Static, Rule-based, PPO, and Multi-Agent."""

import logging
from typing import Dict, Literal, Optional
from backend.app.models.agents import CoordinatorDecision
from backend.app.models.control import ControlAction, ControlDelta
from backend.app.services.environment_service import environment_service
from backend.app.services.qkd_service import qkd_service
from backend.app.services.satellite_service import satellite_service
from ai.agents.coordinator import CoordinatorAgent
from ai.ppo_controller import PPOController
from ai.rule_based_controller import RuleBasedController

logger = logging.getLogger("qsat.control_service")


class ControlService:
    """Orchestrates adaptive controllers and applies control outputs to the optical quantum link."""

    def __init__(self):
        self.rule_based_ctrl = RuleBasedController()
        self.ppo_ctrl = PPOController()
        self.multi_agent_coordinator = CoordinatorAgent()

        self.active_mode: Literal["STATIC", "RULE_BASED", "PPO", "MULTI_AGENT"] = "MULTI_AGENT"

        # Static baseline action
        self._static_action = ControlAction(
            transmission_power_pct=70.0,
            photon_rate_norm=0.80,
            beam_divergence_norm=0.25,
            controller_type="STATIC",
            reason="Fixed static configuration"
        )

        self.latest_action: ControlAction = self._static_action
        self.previous_action: ControlAction = self._static_action
        self.latest_coordinator_decision: Optional[CoordinatorDecision] = None

    def set_controller_type(self, controller_type: Literal["STATIC", "RULE_BASED", "PPO", "MULTI_AGENT"]) -> None:
        """Switch active control policy."""
        self.active_mode = controller_type
        logger.info("Active controller switched to: %s", controller_type)

    def step_control(self) -> ControlAction:
        """Execute one decision step using the active controller and propagate to QKD/Optical link."""
        sat_state = satellite_service.get_state()
        env_state = environment_service.get_current_environment()
        qkd_metrics = qkd_service.get_metrics()
        channel_state = qkd_service.latest_channel_state

        self.previous_action = self.latest_action

        # Run multi-agent coordinator step for telemetry
        coord_decision = self.multi_agent_coordinator.step(
            satellite=sat_state,
            environment=env_state,
            channel=channel_state,
            qkd=qkd_metrics
        )
        self.latest_coordinator_decision = coord_decision

        # Select action based on active controller mode
        if self.active_mode == "STATIC":
            action = self._static_action
        elif self.active_mode == "RULE_BASED":
            action = self.rule_based_ctrl.decide(
                satellite=sat_state,
                environment=env_state,
                channel=channel_state,
                qkd=qkd_metrics
            )
        elif self.active_mode == "PPO":
            action = self.ppo_ctrl.decide(
                satellite=sat_state,
                environment=env_state,
                channel=channel_state,
                qkd=qkd_metrics
            )
        else:  # MULTI_AGENT
            action = coord_decision.final_action

        self.latest_action = action

        # Apply action to QKD link evaluation
        qkd_service.evaluate_current(
            transmission_power_pct=action.transmission_power_pct,
            photon_rate_norm=action.photon_rate_norm,
            beam_divergence_norm=action.beam_divergence_norm
        )

        return self.latest_action

    def get_current_action(self) -> ControlAction:
        return self.latest_action

    def get_current_delta(self) -> ControlDelta:
        return ControlDelta(
            delta_power_pct=round(self.latest_action.transmission_power_pct - self.previous_action.transmission_power_pct, 2),
            delta_photon_rate=round(self.latest_action.photon_rate_norm - self.previous_action.photon_rate_norm, 4),
            delta_beam_divergence=round(self.latest_action.beam_divergence_norm - self.previous_action.beam_divergence_norm, 4),
            controller_type=self.active_mode,
            reason=self.latest_action.reason,
            previous_action=self.previous_action,
            new_action=self.latest_action
        )

    def get_multi_agent_decision(self) -> Optional[CoordinatorDecision]:
        return self.latest_coordinator_decision


# Global singleton instance
control_service = ControlService()
