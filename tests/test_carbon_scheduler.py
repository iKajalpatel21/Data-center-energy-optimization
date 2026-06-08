"""Unit tests for carbon-aware scheduling components."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timezone
from src.scheduling.carbon_scheduler import CarbonTracker, CarbonAwareScheduler, RenewableAwareOptimizer


class TestCarbonTracker:
    def test_default_status_when_empty(self):
        tracker = CarbonTracker(default_carbon_intensity=400)
        status = tracker.get_grid_status()
        assert status["carbon_intensity"] == 400
        assert "status" in status

    def test_records_reading(self):
        tracker = CarbonTracker()
        tracker.add_carbon_reading(
            timestamp=datetime.now(timezone.utc),
            carbon_intensity=250,
            renewable_percentage=60,
        )
        status = tracker.get_grid_status()
        assert status["carbon_intensity"] == 250
        assert status["renewable_percentage"] == 60

    def test_latest_reading_wins(self):
        tracker = CarbonTracker()
        now = datetime.now(timezone.utc)
        tracker.add_carbon_reading(now, 500, 10)
        tracker.add_carbon_reading(now, 150, 80)
        assert tracker.get_grid_status()["carbon_intensity"] == 150

    def test_clean_grid_classification(self):
        tracker = CarbonTracker()
        tracker.add_carbon_reading(datetime.now(timezone.utc), 100, 90)
        status = tracker.get_grid_status()
        assert "Clean" in status["status"] or "clean" in status["status"].lower()

    def test_dirty_grid_classification(self):
        tracker = CarbonTracker()
        tracker.add_carbon_reading(datetime.now(timezone.utc), 600, 5)
        status = tracker.get_grid_status()
        assert status["status"] != "Clean (Good)"


class TestCarbonAwareScheduler:
    def _make_scheduler(self):
        tracker = CarbonTracker(default_carbon_intensity=300)
        tracker.add_carbon_reading(datetime.now(timezone.utc), 300, 40)
        return CarbonAwareScheduler(carbon_tracker=tracker, pue_predictor=None)

    def test_add_workload(self):
        scheduler = self._make_scheduler()
        scheduler.add_workload("job_1", compute_minutes=60, flexibility="flexible")
        assert len(scheduler.workload_queue) == 1
        assert scheduler.workload_queue[0]["job_id"] == "job_1"

    def test_multiple_workloads(self):
        scheduler = self._make_scheduler()
        scheduler.add_workload("j1", 30, "fixed")
        scheduler.add_workload("j2", 120, "deferrable")
        scheduler.add_workload("j3", 60, "flexible")
        assert len(scheduler.workload_queue) == 3

    def test_recommend_scheduling_returns_actions(self):
        scheduler = self._make_scheduler()
        scheduler.add_workload("j1", 60, "deferrable")
        result = scheduler.recommend_scheduling()
        assert "actions" in result
        assert isinstance(result["actions"], list)

    def test_get_stats_structure(self):
        scheduler = self._make_scheduler()
        stats = scheduler.get_stats()
        assert "total_emissions_gco2" in stats


class TestRenewableAwareOptimizer:
    def test_find_best_window_returns_tuple(self):
        optimizer = RenewableAwareOptimizer()
        now = datetime.now(timezone.utc)
        optimizer.update_renewable_forecast(now, {0: 30, 6: 55, 12: 80, 18: 40})
        result = optimizer.find_best_renewable_window(duration_hours=2, minimum_renewable_pct=50)
        assert result is not None
