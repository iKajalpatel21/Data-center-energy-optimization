"""
JSON Schema Validator
Validates incoming data against the defined schemas.
"""

import json
from datetime import datetime
from typing import Dict, Any, Tuple, List
import jsonschema
from jsonschema import validate, ValidationError

from data_schemas import SCHEMAS


class DataValidator:
    """Validates data against JSON schemas with detailed error reporting."""

    def __init__(self):
        self.schemas = SCHEMAS
        self.validation_errors: List[str] = []

    def validate_server_metrics(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate server metrics against schema."""
        return self._validate_against_schema(data, "server_metrics")

    def validate_cooling_metrics(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate cooling metrics against schema."""
        return self._validate_against_schema(data, "cooling_metrics")

    def validate_weather_data(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate weather data against schema."""
        return self._validate_against_schema(data, "weather_data")

    def validate_workload_request(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate workload schedule request against schema."""
        return self._validate_against_schema(data, "workload_schedule_request")

    def _validate_against_schema(
        self, data: Dict[str, Any], schema_name: str
    ) -> Tuple[bool, List[str]]:
        """
        Validate data against specified schema.

        Args:
            data: Data to validate
            schema_name: Name of schema from SCHEMAS dict

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        if schema_name not in self.schemas:
            return False, [f"Schema '{schema_name}' not found"]

        schema = self.schemas[schema_name]

        try:
            validate(instance=data, schema=schema)
            return True, []
        except ValidationError as e:
            errors.append(f"Validation Error: {e.message}")
            errors.append(f"Path: {' -> '.join(str(p) for p in e.path)}")
            return False, errors
        except Exception as e:
            return False, [f"Unexpected error: {str(e)}"]

    @staticmethod
    def validate_timestamp(timestamp_str: str) -> bool:
        """Validate ISO 8601 timestamp format."""
        try:
            datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            return True
        except (ValueError, AttributeError):
            return False

    @staticmethod
    def validate_json_structure(json_str: str) -> Tuple[bool, Dict[str, Any]]:
        """Validate that string is valid JSON."""
        try:
            data = json.loads(json_str)
            return True, data
        except json.JSONDecodeError as e:
            return False, {"error": str(e)}


if __name__ == "__main__":
    # Example usage
    validator = DataValidator()

    # Example server metrics
    sample_metrics = {
        "timestamp": "2026-01-29T12:00:00Z",
        "server_id": "SRV-0001",
        "rack_id": "RACK-A01",
        "zone": "cold_aisle",
        "cpu_utilization": 45.2,
        "memory_utilization": 62.3,
        "power_draw_watts": 850,
        "inlet_temperature_celsius": 18.5,
    }

    is_valid, errors = validator.validate_server_metrics(sample_metrics)
    print(f"Server Metrics Valid: {is_valid}")
    if errors:
        for error in errors:
            print(f"  - {error}")
