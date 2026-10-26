"""Ground station control and actuator API routes."""

from typing import Literal, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field
from backend.app.models.control import ControlAction, ControlDelta
from backend.app.services.control_service import control_service

router = APIRouter(prefix="/api/control", tags=["Control"])


class SwitchControllerRequest(BaseModel):
    controller_type: Optional[Literal["STATIC", "RULE_BASED", "PPO", "MULTI_AGENT"]] = Field(
        None, description="Desired controller type"
    )
    mode: Optional[Literal["STATIC", "RULE_BASED", "PPO", "MULTI_AGENT"]] = Field(
        None, description="Alternative key for desired controller type"
    )

    @property
    def target_mode(self) -> Literal["STATIC", "RULE_BASED", "PPO", "MULTI_AGENT"]:
        val = self.controller_type or self.mode or "MULTI_AGENT"
        return val


@router.get("/current", response_model=ControlAction, summary="Get current actuator control parameters")
async def get_current_control() -> ControlAction:
    """Return active transmission power, photon rate, beam divergence, and decision explanation."""
    return control_service.get_current_action()


@router.get("/delta", response_model=ControlDelta, summary="Get control action delta (Previous -> Current)")
async def get_control_delta() -> ControlDelta:
    """Return changes in actuator parameters from previous to current step with explanation."""
    return control_service.get_current_delta()


@router.post("/mode", summary="Switch active controller type")
@router.post("/switch", summary="Switch active controller type (alias)")
async def set_controller_mode(payload: SwitchControllerRequest):
    """Switch between STATIC, RULE_BASED, PPO, and MULTI_AGENT controllers."""
    mode = payload.target_mode
    control_service.set_controller_type(mode)
    return {"status": "success", "active_controller": mode}


@router.post("/step", response_model=ControlAction, summary="Execute one control decision step")
async def step_control() -> ControlAction:
    """Trigger the active controller to compute and apply the next action."""
    return control_service.step_control()
