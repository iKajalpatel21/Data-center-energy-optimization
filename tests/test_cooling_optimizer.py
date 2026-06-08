"""Unit tests for the cooling optimization engine."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.optimization.cooling_optimizer import CoolingOptimizer


SAMPLE_METRICS = {
    "inlet_temperature": 24.0,
    "outlet_temperature": 29.0,
    "chiller_cop": 3.8,
    "avg_cpu_utilization": 65.0,
}


class TestCoolingOptimizer:
    def test_recommend_setpoint_returns_dict(self):
        opt = CoolingOptimizer()
        rec = opt.recommend_setpoint(
            current_metrics=SAMPLE_METRICS,
            forecasted_pue=1.85,
            forecasted_cpu=70.0,
            outdoor_temp=18.0,
        )
        assert isinstance(rec, dict)
        assert "recommended_setpoint" in rec
        assert "action" in rec

    def test_setpoint_within_bounds(self):
        opt = CoolingOptimizer(min_inlet_temp_celsius=18.0, max_inlet_temp_celsius=27.0)
        rec = opt.recommend_setpoint(SAMPLE_METRICS, 1.5, 30.0, 10.0)
        sp = rec["recommended_setpoint"]
        assert 18.0 <= sp <= 27.0

    def test_high_pue_triggers_more_cooling(self):
        opt = CoolingOptimizer(target_pue_max=1.8)
        rec_ok = opt.recommend_setpoint(SAMPLE_METRICS, 1.6, 50.0, 20.0)
        rec_bad = opt.recommend_setpoint(SAMPLE_METRICS, 2.2, 90.0, 20.0)
        assert rec_bad["recommended_setpoint"] <= rec_ok["recommended_setpoint"]

    def test_chiller_staging_structure(self):
        opt = CoolingOptimizer()
        staging = opt.optimize_chiller_staging(current_load=70.0, outdoor_temp=15.0)
        assert "chillers_to_run" in staging
        assert "action" in staging
        assert staging["chillers_to_run"] >= 1

    def test_chiller_staging_high_load(self):
        opt = CoolingOptimizer()
        staging = opt.optimize_chiller_staging(current_load=95.0, outdoor_temp=25.0)
        assert staging["action"] in ("ADD_CHILLER", "MAINTAIN", "OPTIMAL", "OK")

    def test_chiller_staging_low_load(self):
        opt = CoolingOptimizer()
        staging = opt.optimize_chiller_staging(current_load=20.0, outdoor_temp=10.0, num_chillers=4)
        assert staging["chillers_to_run"] <= 4
