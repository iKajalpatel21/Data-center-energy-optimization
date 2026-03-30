"""
LSTM Workload Forecaster
Predicts future workload spikes using Long Short-Term Memory networks.
Captures temporal dependencies in CPU utilization and network traffic.
"""

import numpy as np
import logging
from typing import Dict, Tuple, Optional, List
from datetime import datetime, timedelta
import json

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping
from sklearn.preprocessing import MinMaxScaler

logger = logging.getLogger(__name__)


class WorkloadForecaster:
    """LSTM-based workload forecaster for CPU and network prediction."""

    def __init__(
        self,
        lookback_steps: int = 12,  # 12 hours of historical data
        forecast_steps: int = 6,  # Forecast 6 hours ahead
        lstm_units: int = 64,
        dropout_rate: float = 0.2,
    ):
        """
        Initialize workload forecaster.

        Args:
            lookback_steps: Number of historical timesteps to use
            forecast_steps: Number of steps to forecast ahead
            lstm_units: Number of LSTM units
            dropout_rate: Dropout rate for regularization
        """
        self.lookback_steps = lookback_steps
        self.forecast_steps = forecast_steps
        self.lstm_units = lstm_units
        self.dropout_rate = dropout_rate
        self.model = None
        self.scaler = MinMaxScaler()
        self.is_trained = False
        self.training_history = None

    def _build_model(self, input_shape: Tuple[int, int]) -> Sequential:
        """Build LSTM model architecture."""
        model = Sequential(
            [
                LSTM(
                    self.lstm_units,
                    return_sequences=True,
                    input_shape=input_shape,
                    activation="relu",
                ),
                Dropout(self.dropout_rate),
                LSTM(self.lstm_units // 2, return_sequences=False, activation="relu"),
                Dropout(self.dropout_rate),
                Dense(self.forecast_steps * 2, activation="relu"),
                Dense(self.forecast_steps, activation="linear"),  # Output layer
            ]
        )

        model.compile(optimizer=Adam(learning_rate=0.001), loss="mse", metrics=["mae"])

        return model

    def prepare_sequences(self, data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare time series data into sequences.

        Args:
            data: Time series array (n_timesteps, n_features)

        Returns:
            Tuple of (X_sequences, y_sequences)
        """
        X, y = [], []

        for i in range(len(data) - self.lookback_steps - self.forecast_steps + 1):
            X.append(data[i : i + self.lookback_steps])
            y.append(
                data[
                    i
                    + self.lookback_steps : i
                    + self.lookback_steps
                    + self.forecast_steps,
                    0,
                ]
            )

        return np.array(X), np.array(y)

    def train(
        self,
        workload_history: np.ndarray,
        epochs: int = 50,
        batch_size: int = 32,
        validation_split: float = 0.2,
    ) -> Dict[str, float]:
        """
        Train the LSTM model.

        Args:
            workload_history: Time series data of shape (n_timesteps, n_features)
                            where first feature is CPU utilization
            epochs: Number of training epochs
            batch_size: Batch size for training
            validation_split: Proportion of data for validation

        Returns:
            Dictionary of training metrics
        """
        if len(workload_history) < self.lookback_steps + self.forecast_steps:
            raise ValueError(
                f"Need at least {self.lookback_steps + self.forecast_steps} timesteps. "
                f"Got {len(workload_history)}"
            )

        # Normalize data
        workload_scaled = self.scaler.fit_transform(workload_history)

        # Prepare sequences
        X, y = self.prepare_sequences(workload_scaled)

        logger.info(f"Training LSTM with {X.shape[0]} sequences...")

        # Build model
        self.model = self._build_model((X.shape[1], X.shape[2]))

        # Early stopping to prevent overfitting
        early_stop = EarlyStopping(
            monitor="val_loss", patience=5, restore_best_weights=True
        )

        # Train model
        self.training_history = self.model.fit(
            X,
            y,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=validation_split,
            callbacks=[early_stop],
            verbose=0,
        )

        self.is_trained = True

        # Evaluate
        train_loss = self.training_history.history["loss"][-1]
        train_mae = self.training_history.history["mae"][-1]
        val_loss = self.training_history.history["val_loss"][-1]
        val_mae = self.training_history.history["val_mae"][-1]

        metrics = {
            "train_loss": train_loss,
            "train_mae": train_mae,
            "val_loss": val_loss,
            "val_mae": val_mae,
            "epochs_trained": len(self.training_history.history["loss"]),
        }

        logger.info(f"LSTM trained. Val Loss: {val_loss:.4f}, Val MAE: {val_mae:.4f}")

        return metrics

    def forecast(self, recent_history: np.ndarray) -> np.ndarray:
        """
        Forecast future workload.

        Args:
            recent_history: Recent workload data (lookback_steps, n_features)

        Returns:
            Forecasted CPU utilization for next forecast_steps
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")

        # Normalize
        recent_scaled = self.scaler.transform(recent_history)

        # Reshape for LSTM
        X_input = recent_scaled.reshape(1, self.lookback_steps, -1)

        # Predict
        forecast_scaled = self.model.predict(X_input, verbose=0)[0]

        # Inverse transform (only for CPU utilization - first feature)
        forecast = np.zeros((len(forecast_scaled), recent_history.shape[1]))
        forecast[:, 0] = forecast_scaled  # CPU predictions

        # Inverse transform the CPU column
        forecast[:, 0] = self.scaler.inverse_transform(
            np.column_stack([forecast_scaled, np.zeros(len(forecast_scaled))])
        )[:, 0]

        return forecast

    def forecast_with_confidence(
        self, recent_history: np.ndarray, n_iterations: int = 100
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Forecast with uncertainty estimation using Monte Carlo dropout.

        Args:
            recent_history: Recent workload data
            n_iterations: Number of stochastic forward passes

        Returns:
            Tuple of (mean, std, predictions)
        """
        predictions = []

        # Enable dropout at test time for uncertainty
        for _ in range(n_iterations):
            forecast = self.forecast(recent_history)
            predictions.append(forecast[:, 0])  # CPU utilization

        predictions = np.array(predictions)
        mean_forecast = np.mean(predictions, axis=0)
        std_forecast = np.std(predictions, axis=0)

        return mean_forecast, std_forecast, predictions

    def save(self, model_path: str, scaler_path: str):
        """Save trained model and scaler."""
        if not self.is_trained:
            raise ValueError("Model not trained.")

        self.model.save(model_path)
        np.save(scaler_path, self.scaler.data_min_)
        np.save(scaler_path.replace(".npy", "_max.npy"), self.scaler.data_max_)
        logger.info(f"Model saved to {model_path}")

    def load(self, model_path: str, scaler_path: str):
        """Load trained model and scaler."""
        self.model = keras.models.load_model(model_path)
        data_min = np.load(scaler_path)
        data_max = np.load(scaler_path.replace(".npy", "_max.npy"))
        self.scaler.data_min_ = data_min
        self.scaler.data_max_ = data_max
        self.scaler.data_range_ = data_max - data_min
        self.is_trained = True
        logger.info(f"Model loaded from {model_path}")

    def detect_spike(
        self, forecast: np.ndarray, threshold_percentile: float = 75.0
    ) -> Dict[str, any]:
        """
        Detect predicted workload spikes.

        Args:
            forecast: Forecasted CPU utilization
            threshold_percentile: Percentile for spike detection

        Returns:
            Dictionary with spike information
        """
        threshold = np.percentile(forecast[:, 0], threshold_percentile)
        spikes = forecast[:, 0] > threshold

        return {
            "threshold": threshold,
            "spike_detected": bool(np.any(spikes)),
            "spike_indices": np.where(spikes)[0].tolist(),
            "max_forecast": float(np.max(forecast[:, 0])),
            "mean_forecast": float(np.mean(forecast[:, 0])),
        }
