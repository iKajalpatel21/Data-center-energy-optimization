"""
Random Forest PUE Predictor
Predicts Power Usage Effectiveness (PUE) using ensemble tree methods.
Lower PUE is better (more efficient cooling).
"""

import numpy as np
import joblib
import logging
from typing import Dict, Any, Tuple, Optional
from datetime import datetime
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error

logger = logging.getLogger(__name__)


class PUEPredictor:
    """Random Forest model for PUE prediction."""

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 15,
        min_samples_split: int = 5,
        random_state: int = 42,
    ):
        """
        Initialize PUE predictor.

        Args:
            n_estimators: Number of trees in the forest
            max_depth: Maximum depth of trees
            min_samples_split: Minimum samples to split a node
            random_state: Random seed for reproducibility
        """
        self.model = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            random_state=random_state,
            n_jobs=-1,
            verbose=0,
        )
        self.scaler = StandardScaler()
        self.feature_names = None
        self.is_trained = False
        self.training_metrics = {}

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        test_size: float = 0.2,
        validation_split: float = 0.1,
    ) -> Dict[str, float]:
        """
        Train the Random Forest model.

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target PUE values (n_samples,)
            test_size: Proportion of data for testing
            validation_split: Proportion of data for validation

        Returns:
            Dictionary of training metrics
        """
        if X.shape[0] < 10:
            logger.warning("Very few samples for training. Results may be unreliable.")

        # Split data: train/val/test
        X_temp, X_test, y_temp, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )

        val_size = validation_split / (1 - test_size)
        X_train, X_val, y_train, y_val = train_test_split(
            X_temp, y_temp, test_size=val_size, random_state=42
        )

        # Normalize features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)
        X_test_scaled = self.scaler.transform(X_test)

        # Train model
        logger.info(f"Training Random Forest with {X_train.shape[0]} samples...")
        self.model.fit(X_train_scaled, y_train)

        # Evaluate on all splits
        train_metrics = self._evaluate_split(X_train_scaled, y_train, "Train")
        val_metrics = self._evaluate_split(X_val_scaled, y_val, "Validation")
        test_metrics = self._evaluate_split(X_test_scaled, y_test, "Test")

        self.training_metrics = {
            "train": train_metrics,
            "validation": val_metrics,
            "test": test_metrics,
        }

        self.is_trained = True
        logger.info(f"Model trained. Test R²: {test_metrics['r2']:.4f}")

        return test_metrics

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict PUE for new samples.

        Args:
            X: Feature matrix

        Returns:
            Predicted PUE values
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")

        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)

    def predict_single(self, features: Dict[str, float], feature_order: list) -> float:
        """
        Predict PUE for a single observation.

        Args:
            features: Dictionary of features
            feature_order: List specifying feature ordering

        Returns:
            Predicted PUE value
        """
        X_single = np.array([[features.get(fname, 0) for fname in feature_order]])
        return self.predict(X_single)[0]

    def get_feature_importance(self, top_n: int = 10) -> Dict[str, float]:
        """
        Get feature importances from the trained model.

        Args:
            top_n: Number of top features to return

        Returns:
            Dictionary of feature names and importance scores
        """
        if not self.is_trained:
            raise ValueError("Model not trained.")

        importances = self.model.feature_importances_
        if self.feature_names is None:
            feature_names = [f"feature_{i}" for i in range(len(importances))]
        else:
            feature_names = self.feature_names

        # Sort by importance
        sorted_idx = np.argsort(importances)[::-1][:top_n]
        return {feature_names[i]: float(importances[i]) for i in sorted_idx}

    def save(self, model_path: str, scaler_path: str):
        """Save trained model and scaler to disk."""
        if not self.is_trained:
            raise ValueError("Model not trained. Cannot save.")

        joblib.dump(self.model, model_path)
        joblib.dump(self.scaler, scaler_path)
        logger.info(f"Model saved to {model_path}")
        logger.info(f"Scaler saved to {scaler_path}")

    def load(self, model_path: str, scaler_path: str):
        """Load trained model and scaler from disk."""
        self.model = joblib.load(model_path)
        self.scaler = joblib.load(scaler_path)
        self.is_trained = True
        logger.info(f"Model loaded from {model_path}")

    def _evaluate_split(
        self, X: np.ndarray, y: np.ndarray, split_name: str
    ) -> Dict[str, float]:
        """Evaluate model on a data split."""
        y_pred = self.model.predict(X)
        mse = mean_squared_error(y, y_pred)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y, y_pred)
        r2 = r2_score(y, y_pred)

        metrics = {
            "mse": mse,
            "rmse": rmse,
            "mae": mae,
            "r2": r2,
        }

        logger.info(f"{split_name} - RMSE: {rmse:.4f}, MAE: {mae:.4f}, R²: {r2:.4f}")

        return metrics
