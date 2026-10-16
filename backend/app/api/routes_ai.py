"""AI and Hierarchical Multi-Agent API routes."""

from typing import Optional
from fastapi import APIRouter
from backend.app.models.agents import CoordinatorDecision
from backend.app.services.control_service import control_service

router = APIRouter(prefix="/api/ai", tags=["AI"])


@router.get("/multi_agent", response_model=Optional[CoordinatorDecision], summary="Get Hierarchical Multi-Agent decisions")
async def get_multi_agent_decision() -> Optional[CoordinatorDecision]:
    """Return latest state from Weather Agent, Communication Agent, Security Agent, and Coordinator."""
    decision = control_service.get_multi_agent_decision()
    if decision is None:
        # Step once to generate initial decision if none exists yet
        control_service.step_control()
        decision = control_service.get_multi_agent_decision()
    return decision


@router.get("/status", summary="Get status of AI models and controllers")
async def get_ai_status():
    """Return operational status for all 4 controllers (Static, Rule-based, PPO, Multi-agent)."""
    ppo_loaded = control_service.ppo_ctrl.model is not None
    return {
        "active_controller": control_service.active_mode,
        "controllers_available": {
            "STATIC": True,
            "RULE_BASED": True,
            "PPO": True,
            "MULTI_AGENT": True
        },
        "ppo_model_loaded": ppo_loaded,
        "multi_agent_active": control_service.active_mode == "MULTI_AGENT"
    }
