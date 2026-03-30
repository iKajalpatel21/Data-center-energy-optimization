"""
Model Training Pipeline
Trains both PUE predictor and workload forecaster on synthetic data.
"""

import sys
import os
import logging
import json
from datetime import datetime, timedelta, timezone
import argparse

import numpy as np
import pandas as pd

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data_generation.synthetic_generator import StreamDataGenerator, DataCenterConfig
from features.feature_engineer import FeatureEngineer
from models.pue_predictor import PUEPredictor
from models.workload_forecaster import WorkloadForecaster

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ModelTrainingPipeline:
    """End-to-end model training pipeline."""

    def __init__(self, output_dir: str = "./models/checkpoints"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.feature_engineer = FeatureEngineer()
        self.pue_predictor = PUEPredictor()
        self.workload_forecaster = WorkloadForecaster()

    def generate_synthetic_data(
        self,
        num_batches: int = 168,  # 1 week of hourly data
        num_servers: int = 50,
    ) -> pd.DataFrame:
        """
        Generate synthetic training data.

        Args:
            num_batches: Number of data batches
            num_servers: Number of servers to simulate

        Returns:
            DataFrame with engineered features
        """
        logger.info(f"Generating {num_batches} batches of synthetic data...")

        config = DataCenterConfig(
            num_servers=num_servers,
            num_racks=5,
            num_chillers=2,
            num_crac_units=4,
        )

        generator = StreamDataGenerator(config)
        start_time = datetime.now(timezone.utc) - timedelta(hours=num_batches)

        for i, batch in enumerate(
            generator.stream_generator(
                start_time=start_time,
                num_batches=num_batches,
                interval_seconds=3600,  # 1 hour intervals
            )
        ):
            self.feature_engineer.process_batch(batch)
            if (i + 1) % 24 == 0:
                logger.info(f"Generated {i + 1}/{num_batches} batches")

        df = self.feature_engineer.get_feature_dataframe()
        logger.info(f"Generated {len(df)} feature records")
        return df

    def train_pue_model(self, df: pd.DataFrame) -> dict:
        """Train Random Forest PUE predictor."""
        logger.info("Training PUE predictor...")

        X, y = self.feature_engineer.get_features_for_training()

        if len(X) < 10:
            logger.error("Insufficient data for training")
            return {}

        metrics = self.pue_predictor.train(X, y)

        # Save model
        model_path = os.path.join(self.output_dir, "pue_model.pkl")
        scaler_path = os.path.join(self.output_dir, "pue_scaler.pkl")
        self.pue_predictor.save(model_path, scaler_path)

        # Get feature importance
        importance = self.pue_predictor.get_feature_importance(top_n=10)
        logger.info(f"Top features: {importance}")

        return {
            "metrics": metrics,
            "feature_importance": importance,
        }

    def train_workload_model(self, df: pd.DataFrame) -> dict:
        """Train LSTM workload forecaster."""
        logger.info("Training workload forecaster...")

        # Prepare workload data (CPU utilization + network)
        workload_cols = ["avg_cpu_utilization", "total_network_in_mbps"]
        workload_data = df[workload_cols].fillna(method="bfill").values

        if len(workload_data) < 30:
            logger.error("Insufficient data for workload training")
            return {}

        metrics = self.workload_forecaster.train(
            workload_data,
            epochs=50,
            batch_size=16,
            validation_split=0.2,
        )

        # Save model
        model_path = os.path.join(self.output_dir, "workload_model.h5")
        scaler_path = os.path.join(self.output_dir, "workload_scaler.npy")
        self.workload_forecaster.save(model_path, scaler_path)

        return {"metrics": metrics}

    def run_pipeline(self, num_batches: int = 168) -> dict:
        """Run complete training pipeline."""
        logger.info("=" * 60)
        logger.info("PHASE 2: ML Models Training Pipeline")
        logger.info("=" * 60)

        # Generate data
        df = self.generate_synthetic_data(num_batches=num_batches)

        # Train models
        pue_results = self.train_pue_model(df)
        workload_results = self.train_workload_model(df)

        # Save results
        results = {
            "timestamp": datetime.now().isoformat(),
            "data_generated": len(df),
            "pue_model": pue_results,
            "workload_model": workload_results,
        }

        results_path = os.path.join(self.output_dir, "training_results.json")
        with open(results_path, "w") as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"Results saved to {results_path}")
        logger.info("=" * 60)
        logger.info("Training complete!")
        logger.info("=" * 60)

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Train ML models for data center optimization"
    )
    parser.add_argument(
        "--batches", type=int, default=168, help="Number of data batches (default: 168)"
    )
    parser.add_argument(
        "--servers", type=int, default=50, help="Number of servers (default: 50)"
    )
    parser.add_argument(
        "--output", type=str, default="./models/checkpoints", help="Output directory"
    )

    args = parser.parse_args()

    pipeline = ModelTrainingPipeline(output_dir=args.output)
    results = pipeline.run_pipeline(num_batches=args.batches)

    print("\n" + "=" * 60)
    print("TRAINING SUMMARY")
    print("=" * 60)
    print(f"Data batches generated: {results['data_generated']}")
    if "metrics" in results.get("pue_model", {}):
        test_metrics = results["pue_model"]["metrics"]
        print(f"PUE Model Test R²: {test_metrics.get('r2', 'N/A'):.4f}")
    if "metrics" in results.get("workload_model", {}):
        wl_metrics = results["workload_model"]["metrics"]
        print(
            f"Workload Model Training Epochs: {wl_metrics.get('epochs_trained', 'N/A')}"
        )
    print("=" * 60)


if __name__ == "__main__":
    main()
