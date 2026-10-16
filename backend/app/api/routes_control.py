"""Ground station control and actuator API routes."""

from typing import Literal
from fastapi import APIRouter
from pydantic import BaseModel, Field
from backend.app.models.control import ControlAction, ControlDelta
from backend.app.services.control_service import control_service

router = APIRouter(prefix="/api/control", tags=["Control"])


class SwitchControllerRequest(BaseModel):
    controller_type: Literal["STATIC", "RULE_BASED", "PPO", "MULTI_AGENT"] = Field(
        ..., description="Desired controller type"
    )


@router.get("/current", response_model=ControlAction, summary="Get current actuator control parameters")
async def get_current_control() -> ControlAction:
    """Return active transmission power, photon rate, beam divergence, and decision explanation."""
    return control_service.get_current_action()


@router.get("/delta", response_model=ControlDelta, summary="Get control action delta (Previous -> Current)")
async def get_control_delta() -> ControlDelta:
    """Return changes in actuator parameters from previous to current step with explanation."""
    return control_service.get_current_delta()


@router.post("/mode", summary="Switch active controller type")
async def set_controller_mode(payload: SwitchControllerRequest):
    """Switch between STATIC, RULE_BASED, PPO, and MULTI_AGENT controllers."""
    control_service.set_controller_type(payload.controller_type)
    return {"status": "success", "active_controller": payload.controller_type}


@router.post("/step", response_model=ControlAction, summary="Execute one control decision step")
async def step_control() -> ControlAction:
    """Trigger the active controller to compute and apply the next action."""
    return control_service.step_control()
