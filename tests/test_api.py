"""Integration tests for the FastAPI REST API."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import numpy as np
from unittest.mock import patch
from fastapi.testclient import TestClient

from src.api.main import app


class _MockPredictor:
    """Minimal stand-in for PUEPredictor and WorkloadForecaster in tests."""
    def predict(self, X):
        return [1.75]

    def forecast_with_confidence(self, X):
        return np.array([60.0] * 6), np.array([5.0] * 6), None

    def detect_spike(self, forecast):
        return {"spike_detected": False, "max_forecast": 65.0}


_mock = _MockPredictor()


@pytest.fixture(scope="module")
def client():
    # Patch model loading before the lifespan wires up the orchestrator
    with patch("src.api.main._load_ml_models", return_value=(_mock, _mock)):
        with TestClient(app) as c:
            yield c


SAMPLE_METRICS = {
    "pue": 1.85,
    "avg_cpu_utilization": 65.0,
    "inlet_temperature": 24.0,
    "outlet_temperature": 29.0,
    "chiller_cop": 3.8,
    "outdoor_temperature_celsius": 18.0,
    "total_network_in_mbps": 5000.0,
}


class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "models_loaded" in data


class TestCarbon:
    def test_get_carbon_default(self, client):
        resp = client.get("/carbon")
        assert resp.status_code == 200
        data = resp.json()
        assert "carbon_intensity" in data

    def test_post_carbon_reading(self, client):
        resp = client.post("/carbon", json={"carbon_intensity": 250.0, "renewable_percentage": 55.0})
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"]["carbon_intensity"] == 250.0

    def test_post_carbon_invalid_renewable(self, client):
        resp = client.post("/carbon", json={"carbon_intensity": 300.0, "renewable_percentage": 150.0})
        assert resp.status_code == 422


class TestWorkloads:
    def test_list_workloads_empty_initially(self, client):
        resp = client.get("/workloads")
        assert resp.status_code == 200
        assert "workloads" in resp.json()

    def test_add_workload(self, client):
        resp = client.post(
            "/workloads",
            json={"job_id": "test-job-1", "compute_minutes": 60, "flexibility": "flexible"},
        )
        assert resp.status_code == 201
        assert resp.json()["job_id"] == "test-job-1"

    def test_add_workload_appears_in_list(self, client):
        client.post("/workloads", json={"job_id": "list-check", "compute_minutes": 30, "flexibility": "deferrable"})
        resp = client.get("/workloads")
        ids = [w["job_id"] for w in resp.json()["workloads"]]
        assert "list-check" in ids

    def test_invalid_flexibility_rejected(self, client):
        resp = client.post(
            "/workloads",
            json={"job_id": "bad-job", "compute_minutes": 30, "flexibility": "whenever"},
        )
        assert resp.status_code == 422


class TestOptimize:
    def test_optimize_returns_result(self, client):
        resp = client.post("/optimize", json={"current_metrics": SAMPLE_METRICS})
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "steps" in data

    def test_optimize_with_carbon_override(self, client):
        resp = client.post(
            "/optimize",
            json={
                "current_metrics": SAMPLE_METRICS,
                "carbon_grid_status": {
                    "carbon_intensity": 180,
                    "renewable_percentage": 70,
                    "status": "Clean (Good)",
                },
            },
        )
        assert resp.status_code == 200


class TestStatus:
    def test_status_after_optimize(self, client):
        client.post("/optimize", json={"current_metrics": SAMPLE_METRICS})
        resp = client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_optimization_cycles"] >= 1
        assert "estimated_cumulative_savings" in data
