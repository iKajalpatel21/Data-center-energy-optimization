"""
Feature Engineering Pipeline
Extracts and transforms raw data center metrics into ML-ready feature matrices.
Handles PUE calculation, temporal features, and normalization.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """Extracts and engineers features from synthetic data."""

    def __init__(self):
        self.feature_history = []

    def process_batch(self, batch: Dict[str, Any]) -> Dict[str, np.ndarray]:
        """
        Process a data center metrics batch into features.

        Args:
            batch: Raw metrics batch from synthetic generator

        Returns:
            Dictionary with feature arrays for modeling
        """
        timestamp_str = batch["timestamp"]
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

        # Extract and aggregate metrics
        server_metrics = batch.get("server_metrics", [])
        cooling_metrics = batch.get("cooling_metrics", [])
        weather_data = batch.get("weather_data", {})

        # Calculate PUE and workload features
        pue_features = self._calculate_pue(server_metrics, cooling_metrics)
        workload_features = self._extract_workload_features(server_metrics)
        cooling_features = self._extract_cooling_features(cooling_metrics, weather_data)
        temporal_features = self._extract_temporal_features(timestamp)
        weather_features = self._extract_weather_features(weather_data)

        # Combine all features
        all_features = {
            **pue_features,
            **workload_features,
            **cooling_features,
            **temporal_features,
            **weather_features,
        }

        # Store in history for time series
        self.feature_history.append({"timestamp": timestamp, "features": all_features})

        return all_features

    def _calculate_pue(
        self, server_metrics: List[Dict], cooling_metrics: List[Dict]
    ) -> Dict[str, float]:
        """
        Calculate PUE (Power Usage Effectiveness).
        PUE = Total Facility Power / IT Equipment Power
        """
        # IT Equipment Power (sum of all server power)
        it_power = sum(m.get("power_draw_watts", 0) for m in server_metrics)

        # Cooling Power (sum of all chiller power)
        cooling_power = sum(
            m.get("chiller_power_consumption_kw", 0) * 1000  # Convert kW to W
            for m in cooling_metrics
        )

        # To estimate total facility power, add 10% overhead (CRAC loss, power distribution, etc)
        overhead_loss = (it_power + cooling_power) * 0.10
        total_facility_power = it_power + cooling_power + overhead_loss

        # Avoid division by zero
        pue = total_facility_power / it_power if it_power > 0 else 1.0

        return {
            "pue": pue,
            "it_power_watts": it_power,
            "cooling_power_watts": cooling_power,
            "total_facility_power_watts": total_facility_power,
            "pue_effectiveness": 1.0
            / pue,  # Lower is better, inverted for easier interpretation
        }

    def _extract_workload_features(
        self, server_metrics: List[Dict]
    ) -> Dict[str, float]:
        """Extract workload-related features from server metrics."""
        if not server_metrics:
            return {
                "avg_cpu_utilization": 0,
                "max_cpu_utilization": 0,
                "std_cpu_utilization": 0,
                "avg_memory_utilization": 0,
                "avg_disk_utilization": 0,
                "total_network_in_mbps": 0,
                "total_network_out_mbps": 0,
                "avg_inlet_temperature": 0,
                "avg_outlet_temperature": 0,
            }

        cpu_vals = [m.get("cpu_utilization", 0) for m in server_metrics]
        memory_vals = [m.get("memory_utilization", 0) for m in server_metrics]
        disk_vals = [m.get("disk_utilization", 0) for m in server_metrics]
        inlet_temps = [m.get("inlet_temperature_celsius", 0) for m in server_metrics]
        outlet_temps = [m.get("outlet_temperature_celsius", 0) for m in server_metrics]
        network_in = [m.get("network_in_mbps", 0) for m in server_metrics]
        network_out = [m.get("network_out_mbps", 0) for m in server_metrics]

        return {
            "avg_cpu_utilization": np.mean(cpu_vals),
            "max_cpu_utilization": np.max(cpu_vals),
            "std_cpu_utilization": np.std(cpu_vals),
            "avg_memory_utilization": np.mean(memory_vals),
            "avg_disk_utilization": np.mean(disk_vals),
            "total_network_in_mbps": np.sum(network_in),
            "total_network_out_mbps": np.sum(network_out),
            "avg_inlet_temperature": np.mean(inlet_temps),
            "avg_outlet_temperature": np.mean(outlet_temps),
            "num_servers": len(server_metrics),
        }

    def _extract_cooling_features(
        self, cooling_metrics: List[Dict], weather_data: Dict
    ) -> Dict[str, float]:
        """Extract cooling system features."""
        if not cooling_metrics:
            return {
                "avg_chiller_cop": 3.5,  # Typical COP
                "avg_chiller_supply_temp": 7.0,
                "avg_chiller_return_temp": 12.0,
                "total_chiller_power_kw": 0,
            }

        cop_vals = [m.get("chiller_efficiency_cop", 3.5) for m in cooling_metrics]
        supply_temps = [
            m.get("chiller_supply_temp_celsius", 7) for m in cooling_metrics
        ]
        return_temps = [
            m.get("chiller_return_temp_celsius", 12) for m in cooling_metrics
        ]
        power_vals = [m.get("chiller_power_consumption_kw", 0) for m in cooling_metrics]

        outdoor_temp = weather_data.get("outdoor_temperature_celsius", 20)

        return {
            "avg_chiller_cop": np.mean(cop_vals),
            "avg_chiller_supply_temp": np.mean(supply_temps),
            "avg_chiller_return_temp": np.mean(return_temps),
            "total_chiller_power_kw": np.sum(power_vals),
            "temp_delta_across_chiller": np.mean(return_temps) - np.mean(supply_temps),
            "outdoor_indoor_temp_diff": np.mean(supply_temps) - outdoor_temp,
        }

    def _extract_temporal_features(self, timestamp: datetime) -> Dict[str, float]:
        """Extract time-based features."""
        hour = timestamp.hour
        day_of_week = timestamp.weekday()
        month = timestamp.month

        # Create cyclical encodings for hour (sine/cosine)
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)

        # Business hours flag
        is_business_hours = 1.0 if 8 <= hour < 18 else 0.0
        is_off_peak = 1.0 if 22 <= hour or hour < 6 else 0.0

        return {
            "hour": float(hour),
            "hour_sin": hour_sin,
            "hour_cos": hour_cos,
            "day_of_week": float(day_of_week),
            "month": float(month),
            "is_business_hours": is_business_hours,
            "is_off_peak": is_off_peak,
            "is_weekend": 1.0 if day_of_week >= 5 else 0.0,
        }

    def _extract_weather_features(self, weather_data: Dict) -> Dict[str, float]:
        """Extract weather-related features."""
        return {
            "outdoor_temperature_celsius": weather_data.get(
                "outdoor_temperature_celsius", 20
            ),
            "outdoor_humidity_percentage": weather_data.get(
                "outdoor_humidity_percentage", 50
            ),
            "dew_point_celsius": weather_data.get("dew_point_celsius", 10),
            "wind_speed_kmh": weather_data.get("wind_speed_kmh", 0),
            "cloud_cover_percentage": weather_data.get("cloud_cover_percentage", 50),
            "solar_irradiance_wm2": weather_data.get("solar_irradiance_wm2", 0),
            "renewable_energy_score": weather_data.get("renewable_energy_score", 0),
        }

    def get_feature_dataframe(self) -> pd.DataFrame:
        """Convert feature history to pandas DataFrame."""
        if not self.feature_history:
            return pd.DataFrame()

        data = []
        for item in self.feature_history:
            row = {"timestamp": item["timestamp"], **item["features"]}
            data.append(row)

        df = pd.DataFrame(data)
        return df.sort_values("timestamp").reset_index(drop=True)

    def get_features_for_training(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get feature vectors and PUE targets for model training.

        Returns:
            Tuple of (X: feature matrix, y: PUE vector)
        """
        df = self.get_feature_dataframe()
        if df.empty:
            return np.array([]), np.array([])

        # Separate target from features
        y = df["pue"].values
        X = df.drop(columns=["timestamp", "pue"]).values

        return X, y
