from typing import Any, Dict, Literal
from pydantic import BaseModel


class SystemStatusResponse(BaseModel):
    system: str
    status: str
    environment_mode: Literal["simulation", "mqtt"]
    version: str


class SystemHealthResponse(BaseModel):
    system: str
    status: str
    environment_mode: Literal["simulation", "mqtt"]
    version: str
    timestamp: str
    uptime_seconds: float
    ground_station: Dict[str, Any]
