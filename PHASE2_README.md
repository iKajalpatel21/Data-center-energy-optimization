"""
Phase 2: ML Models & Feature Engineering
==========================================

This phase introduces machine learning models for data center energy optimization:

1. **Feature Engineering** (src/features/feature_engineer.py)
   - Extracts 40+ features from raw metrics
   - Calculates PUE (Power Usage Effectiveness)
   - Creates temporal, workload, cooling, and weather features
   - Maintains feature history for time series analysis

2. **PUE Predictor** (src/models/pue_predictor.py)
   - Random Forest regressor (100 trees)
   - Predicts Power Usage Effectiveness
   - Feature importance analysis
   - Model persistence (save/load)

3. **Workload Forecaster** (src/models/workload_forecaster.py)
   - LSTM neural network (64 units)
   - 12-hour lookback, 6-hour forecast
   - Spike detection with confidence intervals
   - Monte Carlo dropout for uncertainty estimation

4. **Training Pipeline** (src/ml/train_models.py)
   - End-to-end training automation
   - Synthetic data generation (1 week of hourly data)
   - Model evaluation and persistence
   - Results logging

## Quick Start

Install dependencies:
```bash
pip install -r requirements-producer.txt
```

Train models:
```bash
cd src/ml
python train_models.py --batches 168 --servers 50
```

This will:
- Generate 168 hourly batches of synthetic data
- Engineer features for both models
- Train PUE predictor (Random Forest)
- Train workload forecaster (LSTM)
- Save models to `models/checkpoints/`

## Model Architecture

### Random Forest PUE Predictor
```
- 100 decision trees
- Max depth: 15
- Min samples split: 5
- Input: 40 engineered features
- Output: PUE (1.0 = ideal, 2.0+ = inefficient)
```

### LSTM Workload Forecaster
```
- Layer 1: LSTM (64 units, return_sequences=True)
- Layer 2: LSTM (32 units)
- Layer 3: Dense (12, activation=relu)
- Layer 4: Dense (6, activation=linear)
- Input: 12 timesteps × N features
- Output: 6-step forecast of CPU utilization
```

## Features Engineering

The feature engineer extracts:
- **PUE Metrics**: Total power, IT power, cooling power, effectiveness ratio
- **Workload**: CPU/memory/disk utilization, network throughput, temperatures
- **Cooling System**: Chiller efficiency, temperature deltas
- **Temporal**: Hour of day, day of week, business hours flag
- **Weather**: Outdoor temp, humidity, wind, solar irradiance, renewable score

## Usage Examples

### Train and Evaluate Models
```python
from src.ml.train_models import ModelTrainingPipeline

pipeline = ModelTrainingPipeline()
results = pipeline.run_pipeline(num_batches=168)
```

### Make Predictions
```python
from src.features.feature_engineer import FeatureEngineer
from src.models.pue_predictor import PUEPredictor

engineer = FeatureEngineer()
features = engineer.process_batch(data_batch)

predictor = PUEPredictor()
predictor.load("models/checkpoints/pue_model.pkl", 
               "models/checkpoints/pue_scaler.pkl")
pue_prediction = predictor.predict(X)
```

### Forecast Workload with Uncertainty
```python
from src.models.workload_forecaster import WorkloadForecaster

forecaster = WorkloadForecaster()
forecaster.load("models/checkpoints/workload_model.h5",
                "models/checkpoints/workload_scaler.npy")

# Get forecast with confidence bounds
mean, std, samples = forecaster.forecast_with_confidence(recent_data)
spike_info = forecaster.detect_spike(mean)
```

## Next Steps (Phase 3)

After Phase 2 completion:
- Carbon-aware scheduler using PUE predictions
- Cooling optimization engine
- Renewable energy awareness
- Multi-zone workload distribution
