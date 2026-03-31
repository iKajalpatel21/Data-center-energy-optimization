"""
Real-Time Optimization Orchestrator
Integrates PUE predictions, workload forecasts, carbon awareness,
and cooling optimization into a unified decision engine.
"""

import logging
from typing import Dict, List, Any
from datetime import datetime, timezone
import json

logger = logging.getLogger(__name__)


class OptimizationOrchestrator:
    """Central orchestrator for data center optimization."""

    def __init__(
        self, pue_predictor, workload_forecaster, carbon_scheduler, cooling_optimizer
    ):
        """
        Initialize orchestrator.

        Args:
            pue_predictor: Trained Random Forest PUE model
            workload_forecaster: Trained LSTM workload model
            carbon_scheduler: CarbonAwareScheduler instance
            cooling_optimizer: CoolingOptimizer instance
        """
        self.pue_predictor = pue_predictor
        self.workload_forecaster = workload_forecaster
        self.carbon_scheduler = carbon_scheduler
        self.cooling_optimizer = cooling_optimizer
        self.optimization_log = []

    def optimize(
        self, current_metrics: Dict[str, Any], carbon_grid_status: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run full optimization cycle.

        Args:
            current_metrics: Current data center metrics (from feature engineer)
            carbon_grid_status: Current grid carbon metrics

        Returns:
            Unified optimization recommendation
        """
        timestamp = datetime.now(timezone.utc)

        result = {
            "timestamp": timestamp.isoformat(),
            "status": "OPTIMIZING",
            "steps": [],
        }

        try:
            # Step 1: Predict future PUE
            step1 = self._predict_pue(current_metrics)
            result["steps"].append(step1)

            # Step 2: Forecast workload
            step2 = self._forecast_workload(current_metrics)
            result["steps"].append(step2)

            # Step 3: Carbon-aware scheduling
            step3 = self._optimize_scheduling(
                current_metrics, carbon_grid_status, step2["forecasted_hours"]
            )
            result["steps"].append(step3)

            # Step 4: Cooling optimization
            step4 = self._optimize_cooling(
                current_metrics, step1["predicted_pue"], step2["forecasted_cpu_average"]
            )
            result["steps"].append(step4)

            # Step 5: Synthesize actions
            step5 = self._synthesize_actions(step3, step4, step1, step2)
            result["steps"].append(step5)

            result["status"] = "SUCCESS"
            result["recommendations"] = step5["actions"]
            result["estimated_impact"] = step5["impact"]

        except Exception as e:
            logger.error(f"Optimization error: {e}")
            result["status"] = "ERROR"
            result["error"] = str(e)

        self.optimization_log.append(result)
        return result

    def _predict_pue(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Predict future PUE."""
        try:
            # Extract features (assuming metrics dict contains all features)
            feature_names = list(metrics.keys())
            X = [[metrics.get(name, 0) for name in feature_names]]

            predicted_pue = self.pue_predictor.predict(X)[0]

            return {
                "step": "PUE_PREDICTION",
                "current_pue": metrics.get("pue", 1.5),
                "predicted_pue": predicted_pue,
                "efficiency_trend": (
                    "improving"
                    if predicted_pue < metrics.get("pue", 2.0)
                    else "degrading"
                ),
            }
        except Exception as e:
            logger.error(f"PUE prediction error: {e}")
            return {
                "step": "PUE_PREDICTION",
                "error": str(e),
                "current_pue": metrics.get("pue", 1.5),
            }

    def _forecast_workload(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Forecast future workload."""
        try:
            # Prepare recent history (last 12 hours)
            recent_cpu = metrics.get("avg_cpu_utilization", 50)
            recent_network = metrics.get("total_network_in_mbps", 500)

            # Create mock history for demonstration
            # In production: pull from time series database
            history = [[recent_cpu, recent_network] for _ in range(12)]

            # Forecast next 6 hours
            # This is simplified - actual implementation would use real LSTM
            forecast = [recent_cpu * (1 + 0.1 * (i % 2 - 0.5)) for i in range(6)]

            return {
                "step": "WORKLOAD_FORECAST",
                "forecast_hours": 6,
                "forecasted_cpu_average": sum(forecast) / len(forecast),
                "forecasted_hours": forecast,
                "spike_detected": max(forecast) > recent_cpu + 20,
                "spike_confidence": 0.85 if max(forecast) > recent_cpu + 20 else 0.1,
            }
        except Exception as e:
            logger.error(f"Workload forecast error: {e}")
            return {"step": "WORKLOAD_FORECAST", "error": str(e)}

    def _optimize_scheduling(
        self,
        metrics: Dict[str, Any],
        carbon_status: Dict[str, Any],
        forecasted_hours: List[float],
    ) -> Dict[str, Any]:
        """Generate scheduling recommendations."""
        try:
            # Get carbon-aware scheduling recommendations
            scheduling = self.carbon_scheduler.recommend_scheduling()

            return {
                "step": "SCHEDULING_OPTIMIZATION",
                "current_grid": carbon_status.get("status", "Unknown"),
                "scheduling_actions": scheduling.get("actions", []),
                "total_carbon_emissions_gco2": self.carbon_scheduler.get_stats()[
                    "total_emissions_gco2"
                ],
                "deferrable_saving_potential": "15-30%",
            }
        except Exception as e:
            logger.error(f"Scheduling optimization error: {e}")
            return {"step": "SCHEDULING_OPTIMIZATION", "error": str(e)}

    def _optimize_cooling(
        self, metrics: Dict[str, Any], predicted_pue: float, forecasted_cpu: float
    ) -> Dict[str, Any]:
        """Generate cooling recommendations."""
        try:
            outdoor_temp = metrics.get("outdoor_temperature_celsius", 20)

            # Get setpoint recommendation
            setpoint_rec = self.cooling_optimizer.recommend_setpoint(
                current_metrics=metrics,
                forecasted_pue=predicted_pue,
                forecasted_cpu=forecasted_cpu,
                outdoor_temp=outdoor_temp,
            )

            # Get chiller staging recommendation
            cooling_load = forecasted_cpu * 1.2
            staging_rec = self.cooling_optimizer.optimize_chiller_staging(
                current_load=cooling_load, outdoor_temp=outdoor_temp
            )

            return {
                "step": "COOLING_OPTIMIZATION",
                "setpoint_recommendation": {
                    "current": setpoint_rec["current_setpoint"],
                    "recommended": setpoint_rec["recommended_setpoint"],
                    "action": setpoint_rec["action"],
                    "energy_savings_watts": setpoint_rec.get(
                        "estimated_energy_savings", 0
                    ),
                },
                "chiller_staging": staging_rec,
                "efficiency_outlook": (
                    "Improving" if predicted_pue < 1.8 else "Needs attention"
                ),
            }
        except Exception as e:
            logger.error(f"Cooling optimization error: {e}")
            return {"step": "COOLING_OPTIMIZATION", "error": str(e)}

    def _synthesize_actions(
        self,
        scheduling: Dict[str, Any],
        cooling: Dict[str, Any],
        pue: Dict[str, Any],
        workload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Combine all recommendations into coherent action plan."""
        actions = []

        # Priority 1: Safety (always highest)
        if cooling.get("setpoint_recommendation", {}).get("error"):
            actions.append(
                {
                    "priority": 1,
                    "type": "ALERT",
                    "message": "Cooling system monitoring issue - check integration",
                }
            )

        # Priority 2: Immediate efficiency gains
        setpoint = cooling.get("setpoint_recommendation", {})
        if setpoint.get("energy_savings_watts", 0) > 100:
            actions.append(
                {
                    "priority": 2,
                    "type": "CONTROL",
                    "target": "chiller_setpoint",
                    "action": f"Change to {setpoint.get('recommended', 'auto')}C",
                    "estimated_savings_watts": setpoint.get("energy_savings_watts", 0),
                }
            )

        # Priority 3: Chiller staging
        staging = cooling.get("chiller_staging", {})
        if staging.get("action") in ["ADD_CHILLER", "REDUCE_CHILLERS"]:
            actions.append(
                {
                    "priority": 3,
                    "type": "CONTROL",
                    "target": "chiller_staging",
                    "action": staging["action"],
                    "recommendation": staging.get("recommendation", ""),
                }
            )

        # Priority 4: Workload scheduling based on carbon
        for action in scheduling.get("scheduling_actions", []):
            if action.get("action") in ["DEFER_TO_WINDOW", "DELAY_AND_SCHEDULE"]:
                actions.append(
                    {
                        "priority": 4,
                        "type": "SCHEDULING",
                        "job_id": action.get("job_id"),
                        "action": action["action"],
                        "rationale": action.get("reason", ""),
                    }
                )

        # Calculate impact
        total_power_savings = sum(
            a.get("estimated_savings_watts", 0)
            for a in actions
            if a["type"] == "CONTROL"
        )
        total_emissions_reduction = (
            scheduling.get("total_carbon_emissions_gco2", 0) * 0.2
        )

        impact = {
            "estimated_power_reduction_watts": total_power_savings,
            "estimated_pue_improvement": pue.get("efficiency_trend", "stable"),
            "carbon_reduction_gco2_per_day": total_emissions_reduction * 24,
            "workload_deferral_count": sum(
                1 for a in actions if a["type"] == "SCHEDULING"
            ),
        }

        return {
            "step": "ACTION_SYNTHESIS",
            "actions": actions,
            "impact": impact,
            "priority_order": sorted(actions, key=lambda x: x.get("priority", 999)),
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get overall optimization status summary."""
        if not self.optimization_log:
            return {"status": "No optimizations run yet"}

        successful = sum(1 for o in self.optimization_log if o["status"] == "SUCCESS")
        latest = self.optimization_log[-1]

        return {
            "total_optimization_cycles": len(self.optimization_log),
            "successful_cycles": successful,
            "latest_status": latest.get("status"),
            "latest_timestamp": latest.get("timestamp"),
            "estimated_cumulative_savings": {
                "power_watts": sum(
                    r.get("estimated_impact", {}).get(
                        "estimated_power_reduction_watts", 0
                    )
                    for r in self.optimization_log
                ),
                "carbon_gco2": sum(
                    r.get("estimated_impact", {}).get(
                        "carbon_reduction_gco2_per_day", 0
                    )
                    for r in self.optimization_log
                ),
            },
        }
