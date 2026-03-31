"""
Carbon-Aware Workload Scheduler
Routes compute jobs to periods of low carbon intensity in the grid.
Uses forecasted PUE and renewable energy availability.
"""

import logging
from typing import Dict, List, Any, Tuple
from datetime import datetime, timedelta, timezone
import numpy as np

logger = logging.getLogger(__name__)


class CarbonTracker:
    """Tracks grid carbon intensity and renewable availability."""

    def __init__(self, default_carbon_intensity: float = 400.0):  # gCO2/kWh
        """
        Initialize carbon tracker.

        Args:
            default_carbon_intensity: Default grid carbon intensity (g CO2/kWh)
        """
        self.default_intensity = default_carbon_intensity
        self.carbon_history = []

    def add_carbon_reading(
        self, timestamp: datetime, carbon_intensity: float, renewable_percentage: float
    ):
        """
        Record grid carbon metrics.

        Args:
            timestamp: When measurement was taken
            carbon_intensity: gCO2/kWh (lower is better)
            renewable_percentage: % of grid from renewables (0-100)
        """
        self.carbon_history.append(
            {
                "timestamp": timestamp,
                "intensity": carbon_intensity,
                "renewable_pct": renewable_percentage,
            }
        )

    def get_grid_status(self) -> Dict[str, float]:
        """Get latest grid carbon status."""
        if not self.carbon_history:
            return {
                "carbon_intensity": self.default_intensity,
                "renewable_percentage": 0,
                "status": "Unknown - using defaults",
            }

        latest = self.carbon_history[-1]
        return {
            "carbon_intensity": latest["intensity"],
            "renewable_percentage": latest["renewable_pct"],
            "status": self._classify_grid_status(latest["intensity"]),
        }

    def _classify_grid_status(self, intensity: float) -> str:
        """Classify grid carbon status."""
        if intensity < 200:
            return "Very Clean (Excellent)"
        elif intensity < 300:
            return "Clean (Good)"
        elif intensity < 400:
            return "Moderate"
        elif intensity < 600:
            return "Dirty (Poor)"
        else:
            return "Very Dirty (Critical)"


class CarbonAwareScheduler:
    """Schedules workloads based on grid carbon intensity."""

    def __init__(self, carbon_tracker: CarbonTracker, pue_predictor=None):
        """
        Initialize scheduler.

        Args:
            carbon_tracker: CarbonTracker instance
            pue_predictor: Trained PUE predictor for efficiency estimation
        """
        self.carbon_tracker = carbon_tracker
        self.pue_predictor = pue_predictor
        self.workload_queue = []
        self.scheduled_jobs = []

    def add_workload(
        self,
        job_id: str,
        compute_minutes: int,
        flexibility: str = "flexible",
        carbon_budget: float = None,
    ):
        """
        Add workload to scheduling queue.

        Args:
            job_id: Unique identifier
            compute_minutes: Duration needed
            flexibility: 'fixed' (run now), 'flexible' (delay OK), 'deferrable' (wait for low-carbon)
            carbon_budget: Max acceptable carbon emissions (gCO2)
        """
        workload = {
            "job_id": job_id,
            "compute_minutes": compute_minutes,
            "flexibility": flexibility,
            "carbon_budget": carbon_budget,
            "submit_time": datetime.now(timezone.utc),
            "scheduled": False,
        }
        self.workload_queue.append(workload)
        logger.info(f"Workload added: {job_id} ({flexibility})")

    def recommend_scheduling(self, forecast_hours: int = 24) -> Dict[str, Any]:
        """
        Recommend scheduling for pending workloads.

        Args:
            forecast_hours: Hours ahead to forecast grid status

        Returns:
            Scheduling recommendations
        """
        grid_status = self.carbon_tracker.get_grid_status()
        now = datetime.now(timezone.utc)

        recommendations = {
            "timestamp": now.isoformat(),
            "grid_status": grid_status,
            "actions": [],
        }

        for job in self.workload_queue:
            if job["scheduled"]:
                continue

            if job["flexibility"] == "fixed":
                # Must run now
                action = self._schedule_now(job, grid_status, now)
            elif job["flexibility"] == "flexible":
                # Can wait a bit
                action = self._schedule_flexible(job, grid_status, now)
            else:  # deferrable
                # Wait for best carbon window
                action = self._schedule_deferrable(
                    job, grid_status, now, forecast_hours
                )

            recommendations["actions"].append(action)

        return recommendations

    def _schedule_now(
        self, job: Dict, grid_status: Dict, now: datetime
    ) -> Dict[str, Any]:
        """Schedule job to run immediately."""
        carbon_emissions = self._compute_emissions(
            job["compute_minutes"], grid_status["carbon_intensity"]
        )

        action = {
            "job_id": job["job_id"],
            "action": "SCHEDULE_NOW",
            "reason": "Fixed deadline job",
            "start_time": now.isoformat(),
            "estimated_carbon": carbon_emissions,
            "grid_intensity": grid_status["carbon_intensity"],
        }

        job["scheduled"] = True
        self.scheduled_jobs.append(action)
        return action

    def _schedule_flexible(
        self, job: Dict, grid_status: Dict, now: datetime
    ) -> Dict[str, Any]:
        """Schedule flexible job with small delay if beneficial."""
        carbon_now = self._compute_emissions(
            job["compute_minutes"], grid_status["carbon_intensity"]
        )

        # If grid is reasonably clean, schedule now
        if grid_status["carbon_intensity"] < 350:
            action = {
                "job_id": job["job_id"],
                "action": "SCHEDULE_SOON",
                "delay_minutes": 0,
                "reason": "Grid carbon is acceptable",
                "estimated_carbon": carbon_now,
                "grid_intensity": grid_status["carbon_intensity"],
                "renewable_percentage": grid_status["renewable_percentage"],
            }
        else:
            # Suggest delay for better carbon window
            action = {
                "job_id": job["job_id"],
                "action": "DELAY_AND_SCHEDULE",
                "delay_minutes": 120,  # Suggest 2-hour delay
                "reason": "Grid carbon is high - consider delay for low-carbon window",
                "carbon_reduction_potential": "15-30%",
                "current_intensity": grid_status["carbon_intensity"],
            }

        job["scheduled"] = True
        self.scheduled_jobs.append(action)
        return action

    def _schedule_deferrable(
        self, job: Dict, grid_status: Dict, now: datetime, forecast_hours: int
    ) -> Dict[str, Any]:
        """Schedule deferrable job for optimal carbon window."""
        # Simulate finding best window (in production, use actual forecast)
        best_intensity = (
            grid_status["carbon_intensity"] * 0.7
        )  # Assume 30% improvement possible

        carbon_now = self._compute_emissions(
            job["compute_minutes"], grid_status["carbon_intensity"]
        )
        carbon_optimal = self._compute_emissions(job["compute_minutes"], best_intensity)
        savings = carbon_now - carbon_optimal

        start_window = now + timedelta(hours=2)
        action = {
            "job_id": job["job_id"],
            "action": "DEFER_TO_WINDOW",
            "start_window_time": start_window.isoformat(),
            "window_duration_hours": 4,
            "reason": "Deferrable job - waiting for low-carbon grid period",
            "estimated_carbon_now": carbon_now,
            "estimated_carbon_optimal": carbon_optimal,
            "potential_savings": savings,
            "savings_percentage": (savings / carbon_now * 100) if carbon_now > 0 else 0,
        }

        job["scheduled"] = True
        self.scheduled_jobs.append(action)
        return action

    def _compute_emissions(
        self, compute_minutes: float, carbon_intensity: float, avg_power_kw: float = 5.0
    ) -> float:
        """
        Compute estimated carbon emissions.

        Args:
            compute_minutes: Duration in minutes
            carbon_intensity: Grid carbon intensity (gCO2/kWh)
            avg_power_kw: Average power consumption (kW)

        Returns:
            Estimated emissions in gCO2
        """
        energy_kwh = (compute_minutes / 60.0) * avg_power_kw
        emissions_g_co2 = energy_kwh * carbon_intensity
        return emissions_g_co2

    def get_stats(self) -> Dict[str, Any]:
        """Get scheduling statistics."""
        total_jobs = len(self.workload_queue)
        scheduled = sum(1 for j in self.workload_queue if j["scheduled"])

        total_emissions = sum(
            a.get("estimated_carbon", 0)
            for a in self.scheduled_jobs
            if "estimated_carbon" in a
        )

        return {
            "total_workloads": total_jobs,
            "scheduled": scheduled,
            "pending": total_jobs - scheduled,
            "total_emissions_gco2": total_emissions,
            "avg_emissions_per_job": total_emissions / max(1, scheduled),
        }


class RenewableAwareOptimizer:
    """Routes workloads to periods with high renewable availability."""

    def __init__(self):
        self.renewable_forecast = {}

    def update_renewable_forecast(
        self, timestamp: datetime, forecast_data: Dict[str, float]
    ):
        """
        Update renewable energy availability forecast.

        Args:
            timestamp: Forecast time
            forecast_data: {hour: renewable_percentage, ...}
        """
        self.renewable_forecast[timestamp] = forecast_data

    def find_best_renewable_window(
        self, duration_hours: int, minimum_renewable_pct: float = 50.0
    ) -> Tuple[datetime, float]:
        """
        Find time window with highest renewable availability.

        Args:
            duration_hours: How long the workload needs to run
            minimum_renewable_pct: Minimum acceptable renewable percentage

        Returns:
            Tuple of (recommended_start_time, renewable_percentage)
        """
        best_time = None
        best_percentage = 0

        for timestamp, hourly_data in self.renewable_forecast.items():
            # Calculate average renewable % over duration
            renewable_values = list(hourly_data.values())[:duration_hours]
            avg_renewable = np.mean(renewable_values) if renewable_values else 0

            if (
                avg_renewable >= minimum_renewable_pct
                and avg_renewable > best_percentage
            ):
                best_time = timestamp
                best_percentage = avg_renewable

        if best_time is None:
            # Fall back to current time
            best_time = datetime.now(timezone.utc)
            best_percentage = 0

        return best_time, best_percentage
