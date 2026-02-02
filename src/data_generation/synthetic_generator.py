"""
Synthetic Data Generator for Data Center Metrics
Generates realistic streaming data for server, cooling, and weather metrics.
"""

import json
import random
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Generator
from dataclasses import dataclass
import numpy as np


@dataclass
class DataCenterConfig:
    """Configuration for synthetic data generation."""

    num_servers: int = 100
    num_racks: int = 10
    num_chillers: int = 4
    num_crac_units: int = 8
    base_outdoor_temp: float = 20.0  # Celsius
    base_cpu_utilization: float = 50.0  # Percentage


class SyntheticServerMetricsGenerator:
    """Generates realistic server metrics with temporal patterns."""

    def __init__(self, config: DataCenterConfig = None):
        self.config = config or DataCenterConfig()
        self.servers = self._initialize_servers()
        self.workload_pattern = self._generate_daily_pattern()

    def _initialize_servers(self) -> List[Dict[str, Any]]:
        """Initialize server registry with IDs and rack assignments."""
        servers = []
        for i in range(self.config.num_servers):
            server_id = f"SRV-{i:04d}"
            rack_num = i % self.config.num_racks
            rack_id = f"RACK-{chr(65 + rack_num // 3)}{rack_num % 3:02d}"
            zone = "cold_aisle" if i % 2 == 0 else "hot_aisle"

            servers.append(
                {
                    "id": server_id,
                    "rack_id": rack_id,
                    "zone": zone,
                    "cpu_trend": random.uniform(0.5, 1.5),  # Trend multiplier
                    "last_cpu": self.config.base_cpu_utilization,
                }
            )
        return servers

    def _generate_daily_pattern(self) -> np.ndarray:
        """
        Create a 24-hour load pattern (higher during business hours).
        Returns normalized values (0-1) for each hour.
        """
        hours = np.arange(24)
        # Peak business hours: 8-18 (80-90% load), night hours: 22-6 (30-40% load)
        pattern = 50 + 35 * np.sin((hours - 8) * np.pi / 12)
        pattern = np.clip(pattern, 30, 90)  # Clamp between 30-90
        return pattern / 100  # Normalize to 0-1

    def generate_metrics(
        self, timestamp: datetime, num_records: int = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Generate server metrics for a given timestamp.

        Args:
            timestamp: Reference timestamp (usually now)
            num_records: How many records to generate (default: all servers)

        Yields:
            Individual server metric dictionaries
        """
        num_records = num_records or self.config.num_servers
        hour = timestamp.hour
        base_cpu = self.config.base_cpu_utilization * self.workload_pattern[hour]

        for i in range(num_records):
            server = self.servers[i]

            # CPU utilization with realistic variation
            cpu_base = base_cpu * server["cpu_trend"]
            cpu_noise = random.gauss(0, 5)  # Normal distribution noise
            cpu_utilization = np.clip(cpu_base + cpu_noise, 0, 100)
            server["last_cpu"] = cpu_utilization

            # Memory typically lower than CPU but correlated
            memory_utilization = cpu_utilization * random.uniform(
                0.6, 0.9
            ) + random.gauss(0, 3)
            memory_utilization = np.clip(memory_utilization, 0, 100)

            # Power draw correlation: linear to CPU load
            power_draw_base = 200 + (cpu_utilization / 100) * 600  # 200-800W
            power_draw = power_draw_base + random.gauss(0, 20)

            # Temperature correlation: higher CPU -> higher inlet temp
            inlet_temp = (
                15 + (cpu_utilization / 100) * 20 + random.gauss(0, 1)
            )  # 15-35°C

            outlet_temp = inlet_temp + random.uniform(3, 8)

            # Network varies with workload
            network_in = (cpu_utilization / 100) * 1000 + random.gauss(0, 50)
            network_out = (cpu_utilization / 100) * 800 + random.gauss(0, 40)

            disk_utilization = random.uniform(40, 95)

            yield {
                "timestamp": timestamp.isoformat() + "Z",
                "server_id": server["id"],
                "rack_id": server["rack_id"],
                "zone": server["zone"],
                "cpu_utilization": round(cpu_utilization, 2),
                "memory_utilization": round(memory_utilization, 2),
                "power_draw_watts": round(power_draw, 1),
                "inlet_temperature_celsius": round(inlet_temp, 2),
                "outlet_temperature_celsius": round(outlet_temp, 2),
                "network_in_mbps": round(max(network_in, 0), 2),
                "network_out_mbps": round(max(network_out, 0), 2),
                "disk_utilization": round(disk_utilization, 2),
            }


class SyntheticCoolingMetricsGenerator:
    """Generates realistic cooling system metrics."""

    def __init__(self, config: DataCenterConfig = None):
        self.config = config or DataCenterConfig()
        self.total_server_power = 0

    def generate_metrics(
        self,
        timestamp: datetime,
        avg_cpu_utilization: float,
        outdoor_temp: float = 20.0,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Generate cooling metrics.

        Args:
            timestamp: Reference timestamp
            avg_cpu_utilization: Average CPU utilization across all servers (0-100)
            outdoor_temp: Outside air temperature in Celsius

        Yields:
            Cooling system metric dictionaries
        """
        # Total IT equipment power (rough estimate)
        total_it_power = (
            self.config.num_servers * (200 + (avg_cpu_utilization / 100) * 600) / 1000
        )  # in kW

        for i in range(self.config.num_chillers):
            chiller_id = f"CHILLER-{i:02d}"

            # Chiller load distribution
            chiller_load = total_it_power / self.config.num_chillers + random.gauss(
                0, 5
            )
            chiller_load = max(chiller_load, 10)  # Minimum idle power

            # COP (Coefficient of Performance) varies with outdoor temp
            # Better COP in cooler outdoor conditions
            base_cop = 3.5
            cop = base_cop + (20 - outdoor_temp) * 0.1  # Improves as outside temp drops
            cop = np.clip(cop, 1.5, 6.0)

            # Chiller power consumption: P = Q / COP
            chiller_power = chiller_load / cop + random.gauss(0, 2)

            supply_temp = 8 + random.gauss(0, 0.5)
            return_temp = supply_temp + 4 + random.gauss(0, 0.5)

            yield {
                "timestamp": timestamp.isoformat() + "Z",
                "chiller_id": chiller_id,
                "chiller_power_consumption_kw": round(chiller_power, 2),
                "chiller_efficiency_cop": round(cop, 2),
                "chiller_supply_temp_celsius": round(supply_temp, 2),
                "chiller_return_temp_celsius": round(return_temp, 2),
            }

        # Generate CRAC unit metrics
        for i in range(self.config.num_crac_units):
            crac_id = f"CRAC-{i:02d}"
            crac_power = 15 + random.gauss(0, 3)

            yield {
                "timestamp": timestamp.isoformat() + "Z",
                "crac_unit_id": crac_id,
                "crac_power_consumption_kw": round(crac_power, 2),
            }

        # Calculate aggregate metrics
        total_cooling_power = (
            sum(
                c / cop
                for c in [chiller_load / self.config.num_chillers]
                * self.config.num_chillers
            )
            + self.config.num_crac_units * 15
        )

        # PUE = Total Facility Power / IT Equipment Power
        pue = (
            (total_it_power + total_cooling_power) / total_it_power
            if total_it_power > 0
            else 1.5
        )
        pue = np.clip(pue, 1.0, 5.0)

        # Free cooling opportunity increases as outdoor temp decreases
        free_cooling_percent = max(0, (22 - outdoor_temp) * 10)  # Peaks at 0°C
        free_cooling_percent = min(100, free_cooling_percent)

        data_center_avg_temp = (
            22
            + (avg_cpu_utilization / 100) * 8
            + (outdoor_temp - 20) * 0.5
            + random.gauss(0, 1)
        )

        yield {
            "timestamp": timestamp.isoformat() + "Z",
            "chiller_id": "AGGREGATE",
            "chiller_power_consumption_kw": round(
                sum(
                    total_it_power / self.config.num_chillers
                    for _ in range(self.config.num_chillers)
                )
                / 3.5,
                2,
            ),
            "data_center_pue": round(pue, 3),
            "data_center_average_temp_celsius": round(data_center_avg_temp, 2),
            "data_center_humidity_percentage": round(random.uniform(40, 60), 1),
            "free_cooling_enabled": free_cooling_percent > 20,
            "free_cooling_percentage": round(free_cooling_percent, 1),
            "pump_speed_percentage": round(50 + (avg_cpu_utilization / 100) * 50, 1),
        }


class SyntheticWeatherDataGenerator:
    """Generates realistic weather data from NOAA API patterns."""

    def __init__(self, base_location: Dict[str, float] = None):
        self.base_location = base_location or {
            "latitude": 37.7749,
            "longitude": -122.4194,
            "city": "San Francisco",
            "state": "CA",
        }
        self.current_temp = 20.0
        self.current_temp_trend = random.uniform(-0.5, 0.5)

    def generate_metrics(self, timestamp: datetime) -> Dict[str, Any]:
        """
        Generate weather metrics.

        Args:
            timestamp: Reference timestamp

        Returns:
            Weather metric dictionary
        """
        # Temperature variation throughout the day
        hour = timestamp.hour
        daily_temp_variation = 10 * math.sin((hour - 6) * math.pi / 12)  # Peak at 18:00
        base_temp = 20 + daily_temp_variation

        # Add temporal trend and some random walk
        self.current_temp = base_temp + self.current_temp_trend + random.gauss(0, 0.5)
        self.current_temp_trend += random.gauss(0, 0.1)
        self.current_temp_trend = np.clip(self.current_temp_trend, -2, 2)

        outdoor_temp = self.current_temp
        humidity = 50 + 20 * math.sin((hour - 12) * math.pi / 12) + random.gauss(0, 5)
        humidity = np.clip(humidity, 20, 95)

        # Dew point calculation (simplified)
        dew_point = outdoor_temp - (100 - humidity) / 5

        # Wind patterns (stronger at certain hours)
        wind_base = 10 * math.sin((hour - 6) * math.pi / 12) + 5
        wind_speed = max(0, wind_base + random.gauss(0, 2))
        wind_direction = random.uniform(0, 360)

        # Cloud cover varies inversely with solar irradiance
        cloud_cover = random.uniform(0, 60)
        solar_irradiance = (
            (100 - cloud_cover) * 10 * max(0, math.sin((hour - 6) * math.pi / 12))
        )

        # Renewable energy score (combination of wind and solar)
        renewable_score = (wind_speed / 20) * 50 + (solar_irradiance / 1000) * 50
        renewable_score = min(100, renewable_score)

        # 4-hour forecast (simple: follow current trend)
        forecasted_temp = outdoor_temp + (self.current_temp_trend * 2)

        return {
            "timestamp": timestamp.isoformat() + "Z",
            "data_center_location": self.base_location,
            "outdoor_temperature_celsius": round(outdoor_temp, 2),
            "outdoor_humidity_percentage": round(humidity, 1),
            "dew_point_celsius": round(dew_point, 2),
            "wind_speed_kmh": round(wind_speed, 2),
            "wind_direction_degrees": round(wind_direction, 1),
            "cloud_cover_percentage": round(cloud_cover, 1),
            "solar_irradiance_wm2": round(solar_irradiance, 1),
            "atmospheric_pressure_hpa": round(random.uniform(1010, 1030), 1),
            "forecasted_temperature_4h_celsius": round(forecasted_temp, 2),
            "renewable_energy_score": round(renewable_score, 1),
        }


class StreamDataGenerator:
    """
    Orchestrates generation of all metric types in a realistic streaming fashion.
    """

    def __init__(self, config: DataCenterConfig = None):
        self.config = config or DataCenterConfig()
        self.server_gen = SyntheticServerMetricsGenerator(config)
        self.cooling_gen = SyntheticCoolingMetricsGenerator(config)
        self.weather_gen = SyntheticWeatherDataGenerator()

    def generate_batch(self, timestamp: datetime) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate a complete batch of metrics for a timestamp.

        Args:
            timestamp: Timestamp for all metrics

        Returns:
            Dictionary with 'server_metrics', 'cooling_metrics', 'weather_data' keys
        """
        # Generate all server metrics
        server_metrics = list(self.server_gen.generate_metrics(timestamp))
        avg_cpu = np.mean([m["cpu_utilization"] for m in server_metrics])

        # Generate weather
        weather_data = self.weather_gen.generate_metrics(timestamp)

        # Generate cooling metrics
        cooling_metrics = list(
            self.cooling_gen.generate_metrics(
                timestamp, avg_cpu, weather_data["outdoor_temperature_celsius"]
            )
        )

        return {
            "timestamp": timestamp.isoformat() + "Z",
            "server_metrics": server_metrics,
            "cooling_metrics": cooling_metrics,
            "weather_data": weather_data,
        }

    def stream_generator(
        self,
        start_time: datetime = None,
        num_batches: int = 10,
        interval_seconds: int = 60,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Continuous generator simulating real-time streaming.

        Args:
            start_time: Starting timestamp (default: now)
            num_batches: Number of batches to generate
            interval_seconds: Interval between batches (typically 60)

        Yields:
            Complete metric batches
        """
        start_time = start_time or datetime.now(timezone.utc)
        current_time = start_time

        for _ in range(num_batches):
            yield self.generate_batch(current_time)
            current_time += timedelta(seconds=interval_seconds)


if __name__ == "__main__":
    # Example usage
    config = DataCenterConfig(
        num_servers=10, num_racks=2, num_chillers=2, num_crac_units=2
    )

    generator = StreamDataGenerator(config)

    # Generate a single batch
    batch = generator.generate_batch(datetime.now(timezone.utc))

    print("=== SYNTHETIC DATA BATCH ===")
    print(f"Timestamp: {batch['timestamp']}")
    print(f"\nServer Metrics Count: {len(batch['server_metrics'])}")
    print(f"First Server: {json.dumps(batch['server_metrics'][0], indent=2)}")

    print(f"\nWeather Data: {json.dumps(batch['weather_data'], indent=2)}")

    print(f"\nCooling Metrics Count: {len(batch['cooling_metrics'])}")
    print(f"First Cooling Metric: {json.dumps(batch['cooling_metrics'][0], indent=2)}")
