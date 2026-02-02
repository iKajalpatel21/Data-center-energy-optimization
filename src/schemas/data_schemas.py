"""
Data Schema Definitions for Data Center Energy Optimization
Defines JSON schemas for server metrics, cooling metrics, and weather data.
"""

# Server Metrics Schema
SERVER_METRICS_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Server Metrics",
    "description": "Real-time metrics from individual servers in the data center",
    "type": "object",
    "properties": {
        "timestamp": {
            "type": "string",
            "format": "date-time",
            "description": "UTC timestamp when the metric was recorded (ISO 8601)",
        },
        "server_id": {
            "type": "string",
            "pattern": "^SRV-[0-9]{4}$",
            "description": "Unique server identifier (e.g., SRV-0001)",
        },
        "rack_id": {
            "type": "string",
            "pattern": "^RACK-[A-Z][0-9]{2}$",
            "description": "Rack location (e.g., RACK-A01, RACK-B12)",
        },
        "zone": {
            "type": "string",
            "enum": ["cold_aisle", "hot_aisle"],
            "description": "Temperature zone in the rack",
        },
        "cpu_utilization": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "CPU usage percentage (0-100)",
        },
        "memory_utilization": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "Memory usage percentage (0-100)",
        },
        "power_draw_watts": {
            "type": "number",
            "minimum": 0,
            "maximum": 5000,
            "description": "Instantaneous power consumption in watts",
        },
        "inlet_temperature_celsius": {
            "type": "number",
            "minimum": 10,
            "maximum": 50,
            "description": "Inlet air temperature at server in Celsius",
        },
        "outlet_temperature_celsius": {
            "type": "number",
            "minimum": 15,
            "maximum": 60,
            "description": "Outlet air temperature from server in Celsius",
        },
        "network_in_mbps": {
            "type": "number",
            "minimum": 0,
            "description": "Network inbound throughput in Mbps",
        },
        "network_out_mbps": {
            "type": "number",
            "minimum": 0,
            "description": "Network outbound throughput in Mbps",
        },
        "disk_utilization": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "Disk usage percentage (0-100)",
        },
    },
    "required": [
        "timestamp",
        "server_id",
        "rack_id",
        "cpu_utilization",
        "memory_utilization",
        "power_draw_watts",
        "inlet_temperature_celsius",
    ],
}

# Cooling System Metrics Schema
COOLING_METRICS_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Cooling System Metrics",
    "description": "Cooling infrastructure metrics for the entire data center",
    "type": "object",
    "properties": {
        "timestamp": {
            "type": "string",
            "format": "date-time",
            "description": "UTC timestamp (ISO 8601)",
        },
        "chiller_id": {
            "type": "string",
            "pattern": "^CHILLER-[0-9]{2}$",
            "description": "Chiller unit identifier",
        },
        "chiller_power_consumption_kw": {
            "type": "number",
            "minimum": 0,
            "maximum": 500,
            "description": "Chiller power consumption in kilowatts",
        },
        "chiller_efficiency_cop": {
            "type": "number",
            "minimum": 0.5,
            "maximum": 8,
            "description": "Coefficient of Performance (COP) for the chiller",
        },
        "chiller_supply_temp_celsius": {
            "type": "number",
            "minimum": 2,
            "maximum": 20,
            "description": "Supply water temperature from chiller in Celsius",
        },
        "chiller_return_temp_celsius": {
            "type": "number",
            "minimum": 5,
            "maximum": 30,
            "description": "Return water temperature to chiller in Celsius",
        },
        "crac_unit_id": {
            "type": "string",
            "pattern": "^CRAC-[0-9]{2}$",
            "description": "Computer Room Air Conditioner identifier",
        },
        "crac_power_consumption_kw": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "CRAC unit power consumption in kilowatts",
        },
        "free_cooling_enabled": {
            "type": "boolean",
            "description": "Whether free cooling (outside air) is being utilized",
        },
        "free_cooling_percentage": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "Percentage of cooling load handled by free cooling",
        },
        "data_center_pue": {
            "type": "number",
            "minimum": 1.0,
            "maximum": 5.0,
            "description": "Power Usage Effectiveness (PUE): Total facility power / IT equipment power",
        },
        "data_center_average_temp_celsius": {
            "type": "number",
            "minimum": 15,
            "maximum": 35,
            "description": "Average data center temperature in Celsius",
        },
        "data_center_humidity_percentage": {
            "type": "number",
            "minimum": 20,
            "maximum": 80,
            "description": "Average relative humidity percentage",
        },
        "pump_speed_percentage": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "Cooling water pump speed as percentage of maximum",
        },
    },
    "required": [
        "timestamp",
        "chiller_id",
        "chiller_power_consumption_kw",
        "data_center_pue",
        "data_center_average_temp_celsius",
    ],
}

# Weather Data Schema (from NOAA API)
WEATHER_DATA_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Weather Data",
    "description": "Environmental data from NOAA for free cooling decisions",
    "type": "object",
    "properties": {
        "timestamp": {
            "type": "string",
            "format": "date-time",
            "description": "UTC timestamp (ISO 8601)",
        },
        "data_center_location": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number", "minimum": -90, "maximum": 90},
                "longitude": {"type": "number", "minimum": -180, "maximum": 180},
                "city": {"type": "string"},
                "state": {"type": "string"},
            },
            "required": ["latitude", "longitude"],
        },
        "outdoor_temperature_celsius": {
            "type": "number",
            "minimum": -50,
            "maximum": 60,
            "description": "Outside air temperature in Celsius",
        },
        "outdoor_humidity_percentage": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "Relative humidity percentage",
        },
        "dew_point_celsius": {
            "type": "number",
            "minimum": -50,
            "maximum": 40,
            "description": "Dew point temperature in Celsius",
        },
        "wind_speed_kmh": {
            "type": "number",
            "minimum": 0,
            "maximum": 200,
            "description": "Wind speed in kilometers per hour",
        },
        "wind_direction_degrees": {
            "type": "number",
            "minimum": 0,
            "maximum": 360,
            "description": "Wind direction in degrees (0=N, 90=E, 180=S, 270=W)",
        },
        "cloud_cover_percentage": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "Cloud cover percentage",
        },
        "solar_irradiance_wm2": {
            "type": "number",
            "minimum": 0,
            "maximum": 1500,
            "description": "Solar irradiance in W/m² (proxy for renewable availability)",
        },
        "atmospheric_pressure_hpa": {
            "type": "number",
            "minimum": 850,
            "maximum": 1100,
            "description": "Atmospheric pressure in hectopascals",
        },
        "forecasted_temperature_4h_celsius": {
            "type": "number",
            "minimum": -50,
            "maximum": 60,
            "description": "Temperature forecast for 4 hours ahead",
        },
        "renewable_energy_score": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "Composite score (0-100) for renewable energy availability (solar + wind proxy)",
        },
    },
    "required": [
        "timestamp",
        "data_center_location",
        "outdoor_temperature_celsius",
        "outdoor_humidity_percentage",
        "renewable_energy_score",
    ],
}

# Workload Scheduling Request Schema
WORKLOAD_SCHEDULE_REQUEST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Workload Schedule Request",
    "description": "Request to schedule a batch workload with energy constraints",
    "type": "object",
    "properties": {
        "workload_id": {
            "type": "string",
            "pattern": "^WL-[0-9]{8}$",
            "description": "Unique workload identifier",
        },
        "estimated_duration_minutes": {
            "type": "integer",
            "minimum": 1,
            "maximum": 1440,
            "description": "Expected execution time in minutes",
        },
        "estimated_cpu_load_percentage": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "Expected average CPU utilization across data center",
        },
        "priority": {
            "type": "string",
            "enum": ["critical", "high", "medium", "low"],
            "description": "Business priority level",
        },
        "green_requirement": {
            "type": "string",
            "enum": ["none", "preferred", "required"],
            "description": "Carbon intensity requirement",
        },
        "flexible_scheduling_window_minutes": {
            "type": "integer",
            "minimum": 0,
            "maximum": 1440,
            "description": "How flexible the scheduling window is (0 = must run now)",
        },
    },
    "required": [
        "workload_id",
        "estimated_duration_minutes",
        "estimated_cpu_load_percentage",
        "priority",
    ],
}

# PUE Prediction Target Schema
PUE_PREDICTION_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "PUE Prediction Target",
    "description": "Target variable for Random Forest model training",
    "type": "object",
    "properties": {
        "timestamp": {"type": "string", "format": "date-time"},
        "pue": {
            "type": "number",
            "minimum": 1.0,
            "maximum": 5.0,
            "description": "Actual Power Usage Effectiveness",
        },
        "features": {
            "type": "object",
            "description": "Feature vector used for prediction",
        },
    },
    "required": ["timestamp", "pue"],
}

# Time Series Workload Forecast Schema
WORKLOAD_FORECAST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Workload Forecast",
    "description": "LSTM time-series prediction of upcoming workload spikes",
    "type": "object",
    "properties": {
        "forecast_horizon_minutes": {
            "type": "integer",
            "minimum": 5,
            "maximum": 1440,
            "description": "How far ahead this forecast predicts",
        },
        "predicted_cpu_utilization": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "minutes_ahead": {"type": "integer"},
                    "predicted_utilization_percentage": {"type": "number"},
                    "confidence_interval_upper": {"type": "number"},
                    "confidence_interval_lower": {"type": "number"},
                },
            },
        },
        "spike_detected": {
            "type": "boolean",
            "description": "Whether a significant workload spike is predicted",
        },
        "spike_magnitude_percentage": {
            "type": "number",
            "description": "Expected increase in CPU load percentage",
        },
    },
    "required": ["forecast_horizon_minutes", "predicted_cpu_utilization"],
}

# Dictionary mapping for easy access
SCHEMAS = {
    "server_metrics": SERVER_METRICS_SCHEMA,
    "cooling_metrics": COOLING_METRICS_SCHEMA,
    "weather_data": WEATHER_DATA_SCHEMA,
    "workload_schedule_request": WORKLOAD_SCHEDULE_REQUEST_SCHEMA,
    "pue_prediction": PUE_PREDICTION_SCHEMA,
    "workload_forecast": WORKLOAD_FORECAST_SCHEMA,
}
