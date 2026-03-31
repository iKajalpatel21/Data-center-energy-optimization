"""
Cooling Optimization Engine
Auto-adjusts chiller setpoints and CRAC units based on PUE predictions
and workload forecasts to minimize energy consumption.
"""

import logging
from typing import Dict, List, Any, Tuple
from datetime import datetime, timezone
import numpy as np

logger = logging.getLogger(__name__)


class CoolingOptimizer:
    """Optimizes cooling system setpoints for energy efficiency."""

    def __init__(
        self,
        min_inlet_temp_celsius: float = 18.0,
        max_inlet_temp_celsius: float = 27.0,
        target_pue_max: float = 1.8,
    ):
        """
        Initialize cooling optimizer.

        Args:
            min_inlet_temp_celsius: Minimum safe inlet temperature
            max_inlet_temp_celsius: Maximum safe inlet temperature (ASHRAE limit ~27C)
            target_pue_max: Target PUE - try to keep below this
        """
        self.min_inlet_temp = min_inlet_temp_celsius
        self.max_inlet_temp = max_inlet_temp_celsius
        self.target_pue_max = target_pue_max
        self.current_setpoint = 24.0  # Start at middle
        self.optimization_history = []

    def recommend_setpoint(
        self,
        current_metrics: Dict[str, float],
        forecasted_pue: float,
        forecasted_cpu: float,
        outdoor_temp: float,
    ) -> Dict[str, Any]:
        """
        Recommend optimal inlet temperature setpoint.

        Args:
            current_metrics: Current data center metrics
              - inlet_temperature: Current inlet temp (C)
              - outlet_temperature: Current outlet temp (C)
              - chiller_cop: Current chiller COP
              - avg_cpu: Current CPU utilization %
            forecasted_pue: Predicted PUE in next period
            forecasted_cpu: Predicted CPU utilization %
            outdoor_temp: Current outdoor temperature (C)

        Returns:
            Optimization recommendation
        """
        inlet_temp = current_metrics.get("inlet_temperature", self.current_setpoint)
        outlet_temp = current_metrics.get("outlet_temperature", inlet_temp + 5)
        current_cop = current_metrics.get("chiller_cop", 3.5)
        current_cpu = current_metrics.get("avg_cpu", 50)

        # Calculate temperature margin
        temp_delta = outlet_temp - inlet_temp
        temp_margin = outlet_temp - self.max_inlet_temp

        recommendation = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "current_setpoint": self.current_setpoint,
            "recommended_setpoint": self.current_setpoint,
            "action": "MAINTAIN",
            "rationale": [],
            "estimated_energy_savings": 0,
        }

        # Strategy 1: If PUE is too high, lower setpoint (increase cooling)
        if forecasted_pue > self.target_pue_max:
            new_setpoint = self._lower_setpoint(amount=1.0)
            recommendation["recommended_setpoint"] = new_setpoint
            recommendation["action"] = "INCREASE_COOLING"
            recommendation["rationale"].append(
                f"PUE forecast {forecasted_pue:.2f} exceeds target {self.target_pue_max:.2f}"
            )
            recommendation["rationale"].append(
                "Lower inlet temp improves cooling efficiency"
            )

        # Strategy 2: If forecast shows low CPU usage, raise setpoint (reduce cooling)
        elif forecasted_cpu < 30:
            new_setpoint = self._raise_setpoint(amount=0.5)
            recommendation["recommended_setpoint"] = new_setpoint
            recommendation["action"] = "REDUCE_COOLING"
            recommendation["rationale"].append(
                f"Forecasted CPU {forecasted_cpu:.1f}% is low"
            )
            recommendation["rationale"].append(
                "Reduce cooling load to cut energy consumption"
            )
            savings = self._compute_energy_savings(self.current_setpoint, new_setpoint)
            recommendation["estimated_energy_savings"] = savings

        # Strategy 3: Weather condition optimization
        temp_sensitivity = self._outdoor_temp_sensitivity(outdoor_temp)
        if temp_sensitivity > 0.5:  # Good cooling condition
            new_setpoint = self._raise_setpoint(amount=0.3)
            recommendation["recommended_setpoint"] = new_setpoint
            recommendation["action"] = "AMBIENT_OPTIMIZATION"
            recommendation["rationale"].append(
                f"Outdoor temp {outdoor_temp:.1f}C enables more lenient setpoint"
            )

        # Ensure setpoint stays within bounds
        recommendation["recommended_setpoint"] = np.clip(
            recommendation["recommended_setpoint"],
            self.min_inlet_temp,
            self.max_inlet_temp,
        )

        # Safety check: inlet temp margin
        if temp_margin < 2.0:
            recommendation["safety_warning"] = (
                f"WARNING: Outlet temp {outlet_temp:.1f}C close to max {self.max_inlet_temp}C. "
                "Do not raise setpoint further."
            )
            recommendation["recommended_setpoint"] = self.current_setpoint

        self.optimization_history.append(recommendation)
        self.current_setpoint = recommendation["recommended_setpoint"]

        return recommendation

    def optimize_chiller_staging(
        self, current_load: float, outdoor_temp: float, num_chillers: int = 4
    ) -> Dict[str, Any]:
        """
        Recommend which chillers to run based on load.

        Args:
            current_load: Estimated cooling load (% of capacity)
            outdoor_temp: Current outdoor temperature (C)
            num_chillers: Total number of chillers available

        Returns:
            Chiller staging recommendation
        """
        # Optimal load per chiller: 60-85% (best efficiency)
        optimal_min_load = 0.60
        optimal_max_load = 0.85

        # Calculate number of chillers needed
        chillers_needed = np.ceil(current_load / optimal_max_load)
        chillers_needed = max(1, min(chillers_needed, num_chillers))

        # Calculate load per active chiller
        load_per_chiller = current_load / chillers_needed

        recommendation = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "current_load_percent": current_load,
            "chillers_to_run": int(chillers_needed),
            "load_per_chiller_percent": load_per_chiller,
            "efficiency_status": self._rate_efficiency(load_per_chiller),
            "action": "OK",
        }

        # Check if we should stage differently
        if load_per_chiller < optimal_min_load and chillers_needed > 1:
            recommendation["action"] = "REDUCE_CHILLERS"
            recommendation["recommendation"] = (
                f"Current load allows reducing to {chillers_needed - 1} chillers. "
                "This will improve efficiency."
            )
            recommendation["chillers_to_run"] = int(chillers_needed - 1)

        elif load_per_chiller > optimal_max_load and chillers_needed < num_chillers:
            recommendation["action"] = "ADD_CHILLER"
            recommendation["recommendation"] = (
                f"Load is high. Bringing up additional chiller improves efficiency."
            )

        # Outdoor air effectiveness
        if outdoor_temp < 15:
            recommendation["free_cooling_possible"] = True
            recommendation["recommendation"] = (
                "Consider free cooling or waterside economizer operation"
            )

        return recommendation

    def _lower_setpoint(self, amount: float = 1.0) -> float:
        """Lower the inlet temperature setpoint."""
        new_setpoint = self.current_setpoint - amount
        return max(new_setpoint, self.min_inlet_temp)

    def _raise_setpoint(self, amount: float = 1.0) -> float:
        """Raise the inlet temperature setpoint."""
        new_setpoint = self.current_setpoint + amount
        return min(new_setpoint, self.max_inlet_temp)

    def _outdoor_temp_sensitivity(self, outdoor_temp: float) -> float:
        """
        Rate how beneficial outdoor temperature is for cooling.
        Returns 0-1 where 1 = ideal for economizer operation.
        """
        if outdoor_temp < 10:
            return 0.9  # Very good
        elif outdoor_temp < 15:
            return 0.7
        elif outdoor_temp < 20:
            return 0.5
        else:
            return 0.2  # Not ideal

    def _compute_energy_savings(
        self,
        current_setpoint: float,
        new_setpoint: float,
        watts_per_degree: float = 50.0,
    ) -> float:
        """Estimate energy savings from setpoint change."""
        temp_diff = current_setpoint - new_setpoint
        # Positive diff = lower temp = more cooling = more energy
        # Negative diff = higher temp = less cooling = energy savings
        return -temp_diff * watts_per_degree  # Negative means savings

    def _rate_efficiency(self, load_percent: float) -> str:
        """Rate chiller efficiency at given load."""
        if 60 <= load_percent <= 85:
            return "OPTIMAL"
        elif 50 <= load_percent < 60:
            return "GOOD"
        elif 85 < load_percent <= 95:
            return "GOOD"
        elif load_percent < 50:
            return "POOR (Underloaded)"
        else:
            return "POOR (Overloaded)"


class DynamicCoolingScheduler:
    """Schedules cooling operations based on predicted workload."""

    def __init__(self, workload_forecaster=None):
        """
        Initialize scheduler.

        Args:
            workload_forecaster: Trained LSTM workload forecaster
        """
        self.forecaster = workload_forecaster
        self.cooling_schedule = []

    def generate_cooling_plan(
        self, forecasted_cpu_hours: List[float], planning_horizon_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Generate 24-hour cooling strategy based on workload forecast.

        Args:
            forecasted_cpu_hours: Predicted CPU utilization by hour
            planning_horizon_hours: Hours to plan ahead

        Returns:
            Hour-by-hour cooling recommendations
        """
        plan = {
            "planning_period": f"{planning_horizon_hours}h",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "hourly_schedule": [],
        }

        for hour, cpu_forecast in enumerate(
            forecasted_cpu_hours[:planning_horizon_hours]
        ):
            # Map CPU to cooling load (conservative: load = CPU * 1.2)
            cooling_load = min(cpu_forecast * 1.2, 100)

            hour_plan = {
                "hour": hour,
                "forecasted_cpu": cpu_forecast,
                "estimated_cooling_load": cooling_load,
                "recommended_setpoint": self._compute_setpoint_for_load(cooling_load),
                "predicted_cop": self._estimate_cop(cooling_load),
                "action": self._action_for_load(cooling_load),
            }

            plan["hourly_schedule"].append(hour_plan)

        return plan

    def _compute_setpoint_for_load(self, load_percent: float) -> float:
        """Compute optimal setpoint for given cooling load."""
        # Linear interpolation: 30% load @ 26C, 80% load @ 19C
        if load_percent < 30:
            return 26.0
        elif load_percent > 80:
            return 19.0
        else:
            # Linear scaling
            return 26.0 - (load_percent - 30) * (7.0 / 50.0)

    def _estimate_cop(self, load_percent: float) -> float:
        """Estimate chiller COP at given load (typical profile)."""
        # Chillers are most efficient at 60-80% load
        if 60 <= load_percent <= 80:
            return 4.2
        elif 40 <= load_percent < 60:
            return 3.8
        elif 80 < load_percent <= 100:
            return 3.5
        else:
            return 2.5  # Low efficiency at very low load

    def _action_for_load(self, load_percent: float) -> str:
        """Determine action for current load level."""
        if load_percent > 90:
            return "MAXCOOLING"
        elif load_percent > 60:
            return "NORMALCOOLING"
        elif load_percent > 30:
            return "REDUCEDCOOLING"
        else:
            return "STANDBY"
