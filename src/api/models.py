"""Pydantic request/response models for the optimization API."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CarbonReadingRequest(BaseModel):
    carbon_intensity: float = Field(..., description="Grid carbon intensity in gCO2/kWh")
    renewable_percentage: float = Field(..., ge=0, le=100, description="% of grid from renewables")


class WorkloadRequest(BaseModel):
    job_id: str = Field(..., description="Unique job identifier")
    compute_minutes: int = Field(..., gt=0, description="Estimated compute time in minutes")
    flexibility: str = Field(
        default="flexible",
        description="Scheduling flexibility: fixed | flexible | deferrable",
    )


class OptimizeRequest(BaseModel):
    current_metrics: Dict[str, float] = Field(
        ..., description="Current data center metrics (feature-engineered values)"
    )
    carbon_grid_status: Optional[Dict[str, Any]] = Field(
        default=None, description="Override carbon grid status; uses last recorded reading if omitted"
    )


class HealthResponse(BaseModel):
    status: str
    version: str
    models_loaded: bool


class StatusResponse(BaseModel):
    total_optimization_cycles: int
    successful_cycles: int
    estimated_cumulative_savings: Dict[str, float]
    carbon_grid_status: Dict[str, Any]
    pending_workloads: int
