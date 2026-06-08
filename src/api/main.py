"""
Data Center Energy Optimization - REST API
Phase 4: Wraps the Phase 3 optimization orchestrator as an HTTP service.
"""

import logging
import sys
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

# Allow running from repo root or src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.scheduling.carbon_scheduler import CarbonTracker, CarbonAwareScheduler
from src.optimization.cooling_optimizer import CoolingOptimizer
from src.optimization.orchestrator import OptimizationOrchestrator
from src.api.models import (
    CarbonReadingRequest,
    WorkloadRequest,
    OptimizeRequest,
    HealthResponse,
    StatusResponse,
)

logger = logging.getLogger(__name__)

VERSION = "4.0.0"

# ---------------------------------------------------------------------------
# Shared application state
# ---------------------------------------------------------------------------

class AppState:
    orchestrator: Optional[OptimizationOrchestrator] = None
    carbon_tracker: Optional[CarbonTracker] = None
    carbon_scheduler: Optional[CarbonAwareScheduler] = None
    cooling_optimizer: Optional[CoolingOptimizer] = None
    models_loaded: bool = False


app_state = AppState()


def _load_ml_models():
    """Load trained ML models if checkpoints exist; return (pue, lstm) or (None, None)."""
    try:
        from src.models.pue_predictor import PUEPredictor
        from src.models.workload_forecaster import WorkloadForecaster

        pue_model_path = "models/checkpoints/pue_model.pkl"
        pue_scaler_path = "models/checkpoints/pue_scaler.pkl"
        lstm_model_path = "models/checkpoints/workload_model.h5"
        lstm_scaler_path = "models/checkpoints/workload_scaler.npy"

        if not (
            os.path.exists(pue_model_path)
            and os.path.exists(pue_scaler_path)
            and os.path.exists(lstm_model_path)
            and os.path.exists(lstm_scaler_path)
        ):
            logger.warning("Model checkpoints not found — running without ML models")
            return None, None

        pue = PUEPredictor()
        pue.load(pue_model_path, pue_scaler_path)

        lstm = WorkloadForecaster()
        lstm.load(lstm_model_path, lstm_scaler_path)

        logger.info("ML models loaded successfully")
        return pue, lstm

    except Exception as exc:
        logger.warning("Could not load ML models: %s", exc)
        return None, None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    pue_model, lstm_model = _load_ml_models()
    app_state.models_loaded = pue_model is not None

    app_state.carbon_tracker = CarbonTracker(default_carbon_intensity=400.0)
    app_state.carbon_scheduler = CarbonAwareScheduler(
        carbon_tracker=app_state.carbon_tracker,
        pue_predictor=pue_model,
    )
    app_state.cooling_optimizer = CoolingOptimizer(target_pue_max=1.8)
    app_state.orchestrator = OptimizationOrchestrator(
        pue_predictor=pue_model,
        workload_forecaster=lstm_model,
        carbon_scheduler=app_state.carbon_scheduler,
        cooling_optimizer=app_state.cooling_optimizer,
    )

    logger.info("Optimization service started (models_loaded=%s)", app_state.models_loaded)
    yield
    # Shutdown (nothing to clean up)


app = FastAPI(
    title="Data Center Energy Optimization API",
    description=(
        "Phase 4 REST API wrapping the ML-powered optimization orchestrator. "
        "Exposes carbon-aware scheduling, cooling optimization, and PUE prediction."
    ),
    version=VERSION,
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Health & status
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["system"])
def health():
    """Returns service liveness and model availability."""
    return HealthResponse(
        status="ok",
        version=VERSION,
        models_loaded=app_state.models_loaded,
    )


@app.get("/status", response_model=StatusResponse, tags=["system"])
def get_status():
    """Returns cumulative optimization statistics."""
    summary = app_state.orchestrator.get_summary()
    return StatusResponse(
        total_optimization_cycles=summary.get("total_optimization_cycles", 0),
        successful_cycles=summary.get("successful_cycles", 0),
        estimated_cumulative_savings=summary.get("estimated_cumulative_savings", {}),
        carbon_grid_status=app_state.carbon_tracker.get_grid_status(),
        pending_workloads=len(app_state.carbon_scheduler.workload_queue),
    )


# ---------------------------------------------------------------------------
# Carbon grid
# ---------------------------------------------------------------------------

@app.get("/carbon", tags=["carbon"])
def get_carbon():
    """Returns the latest recorded carbon grid status."""
    return app_state.carbon_tracker.get_grid_status()


@app.post("/carbon", status_code=status.HTTP_201_CREATED, tags=["carbon"])
def update_carbon(body: CarbonReadingRequest):
    """Record a new carbon intensity reading for the grid."""
    app_state.carbon_tracker.add_carbon_reading(
        timestamp=datetime.now(timezone.utc),
        carbon_intensity=body.carbon_intensity,
        renewable_percentage=body.renewable_percentage,
    )
    return {"message": "Carbon reading recorded", "status": app_state.carbon_tracker.get_grid_status()}


# ---------------------------------------------------------------------------
# Workloads
# ---------------------------------------------------------------------------

@app.get("/workloads", tags=["workloads"])
def list_workloads():
    """Lists all workloads currently in the scheduling queue."""
    queue = app_state.carbon_scheduler.workload_queue
    return {
        "count": len(queue),
        "workloads": [
            {
                "job_id": w["job_id"],
                "compute_minutes": w["compute_minutes"],
                "flexibility": w["flexibility"],
                "submitted_at": w["submitted_at"].isoformat()
                if hasattr(w.get("submitted_at"), "isoformat")
                else w.get("submitted_at"),
            }
            for w in queue
        ],
    }


@app.post("/workloads", status_code=status.HTTP_201_CREATED, tags=["workloads"])
def add_workload(body: WorkloadRequest):
    """Add a compute workload to the carbon-aware scheduling queue."""
    valid_flexibilities = {"fixed", "flexible", "deferrable"}
    if body.flexibility not in valid_flexibilities:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"flexibility must be one of {valid_flexibilities}",
        )
    app_state.carbon_scheduler.add_workload(
        job_id=body.job_id,
        compute_minutes=body.compute_minutes,
        flexibility=body.flexibility,
    )
    return {"message": f"Workload '{body.job_id}' queued", "job_id": body.job_id}


# ---------------------------------------------------------------------------
# Optimization
# ---------------------------------------------------------------------------

@app.post("/optimize", tags=["optimization"])
def run_optimization(body: OptimizeRequest):
    """
    Run a full optimization cycle.

    Accepts current data center metrics and returns cooling setpoint
    recommendations, scheduling actions, PUE predictions, and estimated
    energy/carbon impact.
    """
    carbon_status = body.carbon_grid_status or app_state.carbon_tracker.get_grid_status()

    result = app_state.orchestrator.optimize(
        current_metrics=body.current_metrics,
        carbon_grid_status=carbon_status,
    )

    if result.get("status") == "ERROR":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Optimization failed"),
        )

    return result
